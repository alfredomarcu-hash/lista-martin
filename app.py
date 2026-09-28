"""
Lista de Martín — lista de regalos para el bebé, sin necesidad de cuenta
para quien la visita. Lee y escribe directamente en un Google Sheet
mediante una cuenta de servicio (igual que la Mundoporra).
"""

import datetime as dt
import html
import re
import unicodedata

import gspread
import streamlit as st
from google.oauth2.service_account import Credentials

# --------------------------------------------------------------------------
# Configuración
# --------------------------------------------------------------------------

BABY_NAME = "Martín"

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

SOURCE_SHEET = "Hoja 1"  # la hoja de trabajo original de Alfredo: fuente de verdad
SHEET_ITEMS = "APP_datos"  # generada y mantenida automáticamente por la app
SHEET_PURCHASES = "APP_compras"

ITEMS_HEADER = [
    "id", "seccion", "nombre", "detalle", "link", "precio", "necesarias", "compradas", "en_lista",
]
PURCHASES_HEADER = ["fecha", "item_id", "nombre_comprador", "cantidad", "importe"]

SECTION_ORDER = [
    "Dormitorio", "Textil", "Baño", "Lactancia", "Alimentación",
    "Salón", "Paseo", "Coche", "Estimulación sensorial",
]

# APP_datos ya no se siembra a mano: se genera y mantiene sola a partir de
# "Hoja 1" (ver sync_from_source más abajo). Si la pestaña no existe todavía,
# se crea vacía, solo con la cabecera.

# --------------------------------------------------------------------------
# Conexión con Google Sheets
# --------------------------------------------------------------------------

@st.cache_resource(show_spinner=False)
def get_client():
    info = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    return gspread.authorize(creds)


@st.cache_resource(show_spinner=False)
def get_spreadsheet():
    client = get_client()
    return client.open_by_key(st.secrets["spreadsheet_id"])


def ensure_sheets():
    ss = get_spreadsheet()
    titles = [ws.title for ws in ss.worksheets()]

    if SHEET_ITEMS not in titles:
        ws = ss.add_worksheet(title=SHEET_ITEMS, rows=100, cols=len(ITEMS_HEADER))
        ws.update([ITEMS_HEADER], "A1")

    if SHEET_PURCHASES not in titles:
        ws = ss.add_worksheet(title=SHEET_PURCHASES, rows=500, cols=len(PURCHASES_HEADER))
        ws.update([PURCHASES_HEADER], "A1")


def _normalize_header(h):
    """'SECCIÓN' -> 'SECCION', 'LINK PRODUCTO' -> 'LINK_PRODUCTO', etc. Lets us
    match Hoja 1's headers without worrying about acentos/espacios/mayúsculas."""
    h = str(h).strip()
    h = unicodedata.normalize("NFKD", h).encode("ascii", "ignore").decode("ascii")
    h = h.upper()
    h = re.sub(r"[^A-Z0-9]+", "_", h).strip("_")
    return h


def slugify(text, max_len=60):
    """Genera un id estable y legible a partir de texto libre (sección +
    nombre), para poder actualizar siempre la misma fila en APP_datos aunque
    se repita la sincronización."""
    text = str(text).strip()
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return (text[:max_len].strip("-")) or "articulo"


def _parse_precio_range(raw):
    """Convierte un precio en float, tolerando el formato español.

    - '15,99'  -> 15.99   (coma decimal)
    - '29.99'  -> 29.99   (punto decimal)
    - '1.234,56' -> 1234.56 (punto de miles + coma decimal)
    - '885 - 935' -> 885.0  (se queda con el primer número)
    - '369 + 69 + 49' -> 369.0

    Ojo: es imprescindible interpretar bien la coma. La conversión
    automática de Google/gspread trata '29,99' como 2999 (mil separadores),
    de ahí que antes aparecieran "miles de euros"."""
    m = re.search(r"\d[\d.,]*", str(raw))
    if not m:
        return 0.0
    tok = m.group(0)
    if "." in tok and "," in tok:
        # Están los dos: el ÚLTIMO que aparece es el separador decimal.
        if tok.rfind(",") > tok.rfind("."):
            tok = tok.replace(".", "").replace(",", ".")  # 1.234,56 -> 1234.56
        else:
            tok = tok.replace(",", "")                     # 1,234.56 -> 1234.56
    elif "," in tok:
        tok = tok.replace(",", ".")                        # 29,99 -> 29.99
    try:
        return float(tok)
    except ValueError:
        return 0.0


def _first_line(text):
    """Primera línea no vacía de un texto (se usa para el id y como nombre
    de reserva cuando falta el sub-elemento)."""
    for line in str(text).splitlines():
        line = line.strip(" -—\t")
        if line:
            return line
    return ""


_VISIBLE_VALUES = ("sí", "si", "true", "1", "x", "yes")


def sync_from_source():
    """Lee 'Hoja 1' (la fuente de verdad de Alfredo), se queda con las filas
    marcadas como visibles en su columna EN_LISTA, y actualiza APP_datos para
    que coincida — sin tocar nunca 'compradas' de lo que ya existía."""
    ss = get_spreadsheet()
    titles = [ws.title for ws in ss.worksheets()]
    if SOURCE_SHEET not in titles:
        return  # nada que sincronizar todavía

    ws_src = ss.worksheet(SOURCE_SHEET)
    src_values = ws_src.get_all_values()
    if not src_values:
        return

    header = [_normalize_header(h) for h in src_values[0]]

    def col_index(*names):
        for name in names:
            if name in header:
                return header.index(name)
        return None

    idx_seccion = col_index("SECCION")
    idx_elemento = col_index("ELEMENTO")
    idx_sub = col_index("SUB_ELEMENTO")
    idx_descripcion = col_index("DESCRIPCION")
    idx_link = col_index("LINK_PRODUCTO")
    idx_precio = col_index("PRECIO")
    idx_en_lista = col_index("EN_LISTA")
    idx_cantidad = col_index("CANTIDAD")
    # Nota: la columna "COMENTARIOS (no incluir en Claude)" es privada de
    # Alfredo y su pareja. No se lee nunca: no se usa ni para el detalle,
    # ni para el id, ni para nada — solo se muestra DESCRIPCIÓN.

    if idx_en_lista is None:
        return  # Alfredo aún no ha añadido la columna EN LISTA en Hoja 1

    def cell(row, idx):
        return row[idx].strip() if idx is not None and idx < len(row) else ""

    visible_rows = []
    seen_ids = {}
    for row in src_values[1:]:
        if cell(row, idx_en_lista).lower() not in _VISIBLE_VALUES:
            continue
        elemento = cell(row, idx_elemento)
        sub = cell(row, idx_sub)
        descripcion = cell(row, idx_descripcion)
        # SUB-ELEMENTO es el producto concreto (p.ej. "Minicuna", "Hamaca",
        # "Sillita"); ELEMENTO suele ser solo la categoría ("Cuna", "Asiento").
        # El nombre de cara a la familia es el producto, no la categoría.
        nombre = sub or elemento or _first_line(descripcion)
        link = cell(row, idx_link)
        precio_raw = cell(row, idx_precio)
        # El link es OPCIONAL: algunos regalos son "packs" o ideas sin una
        # página concreta (canastillas de ropa por edad, sets de estimulación).
        # Basta con que tengan nombre, precio y estén marcados en la lista.
        if not nombre or not precio_raw:
            continue
        seccion = cell(row, idx_seccion) or "Otros"
        necesarias = max(1, _to_int(cell(row, idx_cantidad), default=1))
        # El id se construye con la primera línea de la DESCRIPCIÓN (la marca)
        # y el precio para que dos productos con el mismo sub-elemento (p.ej.
        # varias "Muselinas" de marcas o tamaños distintos) no colisionen.
        base_id = slugify(f"{seccion}-{elemento}-{sub}-{_first_line(descripcion)}-{precio_raw}")
        item_id = base_id
        if item_id in seen_ids:
            seen_ids[base_id] += 1
            item_id = f"{base_id}-{seen_ids[base_id]}"
        else:
            seen_ids[base_id] = 1
        # Solo enlazamos si es una URL de verdad (no una marca suelta como
        # "Mustela" que Alfredo pueda dejar en la casilla del link).
        link = link if link.lower().startswith("http") else ""
        visible_rows.append({
            "id": item_id,
            "seccion": seccion,
            "nombre": nombre,
            "detalle": descripcion,
            "link": link,
            "precio": _parse_precio_range(precio_raw),
            "necesarias": necesarias,
        })

    ws_items = ss.worksheet(SHEET_ITEMS)
    items_values = ws_items.get_all_values()

    # Antes de reescribir, guardamos las unidades ya compradas por id, para no
    # perderlas si una fila sigue existiendo tras la sincronización.
    compradas_by_id = {}
    if items_values:
        old_header = items_values[0]
        if "id" in old_header and "compradas" in old_header:
            id_i = old_header.index("id")
            comp_i = old_header.index("compradas")
            for row in items_values[1:]:
                if id_i < len(row) and row[id_i].strip():
                    val = row[comp_i] if comp_i < len(row) else 0
                    compradas_by_id[row[id_i].strip()] = _to_int(val, default=0)

    # Reconstruimos APP_datos entero: cabecera + exactamente las filas marcadas
    # como visibles en Hoja 1, en su mismo orden. Así APP_datos es siempre un
    # reflejo limpio de la lista pública, sin filas viejas acumuladas. El
    # histórico completo de compras vive aparte en APP_compras, de modo que
    # esta reescritura nunca pierde información.
    col = {name: i for i, name in enumerate(ITEMS_HEADER)}
    out_rows = [list(ITEMS_HEADER)]
    for item in visible_rows:
        row = [""] * len(ITEMS_HEADER)
        row[col["id"]] = item["id"]
        row[col["seccion"]] = item["seccion"]
        row[col["nombre"]] = item["nombre"]
        row[col["detalle"]] = item["detalle"]
        row[col["link"]] = item["link"]
        row[col["precio"]] = item["precio"]
        row[col["necesarias"]] = item["necesarias"]
        row[col["compradas"]] = compradas_by_id.get(item["id"], 0)
        row[col["en_lista"]] = "sí"
        out_rows.append(row)

    ws_items.clear()
    ws_items.update(out_rows, "A1")


@st.cache_data(ttl=30, show_spinner=False)
def sync_from_source_cached():
    """Limita la sincronización a como mucho una vez cada 30s en todo el
    servidor (no por visitante), para no agotar la cuota de la API de Sheets."""
    sync_from_source()
    return dt.datetime.now().isoformat()


def _is_visible(record):
    """True unless the sheet has an 'en_lista' column that explicitly says
    no for this row. Rows added before the column existed (or a sheet that
    never adds it) stay visible, so this is backward compatible."""
    if "en_lista" not in record:
        return True
    raw = str(record.get("en_lista", "")).strip().lower()
    return raw in ("sí", "si", "true", "1", "x", "yes")


def _to_float(value, default=0.0):
    try:
        return float(str(value).replace(",", ".").strip())
    except (TypeError, ValueError):
        return default


def _to_int(value, default=0):
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return default


@st.cache_data(ttl=8, show_spinner=False)
def load_items():
    ss = get_spreadsheet()
    ws = ss.worksheet(SHEET_ITEMS)
    # numericise_ignore=["all"]: leemos todo como texto tal cual. Si dejamos
    # que gspread "numerice", convierte "29,99" en 2999 (interpreta la coma
    # como separador de miles) y aparecían precios de miles de euros.
    rows = ws.get_all_records(numericise_ignore=["all"])
    items = []
    for r in rows:
        item_id = str(r.get("id", "")).strip()
        if not item_id:
            continue  # a blank row, or one still missing its id
        if not _is_visible(r):
            continue  # marked as internal-only (en_lista != sí)

        precio = _parse_precio_range(r.get("precio"))
        link = str(r.get("link", "")).strip()
        necesarias = _to_int(r.get("necesarias"), default=1) or 1

        if precio <= 0:
            continue  # sin precio todavía: aún no se puede reservar
        # El link es opcional (hay regalos sin página concreta, como packs).

        items.append({
            "id": item_id,
            "seccion": str(r.get("seccion", "")).strip() or "Otros",
            "nombre": str(r.get("nombre", "")).strip() or item_id,
            "detalle": str(r.get("detalle", "")).strip(),
            "link": link,
            "precio": precio,
            "necesarias": necesarias,
            "compradas": _to_int(r.get("compradas"), default=0),
        })
    return items


def remaining(item):
    return max(0, item["necesarias"] - item["compradas"])


def group_by_section(items):
    visible = [it for it in items if remaining(it) > 0]
    by_section = {}
    for it in visible:
        by_section.setdefault(it["seccion"], []).append(it)
    ordered = [s for s in SECTION_ORDER if s in by_section]
    ordered += [s for s in by_section if s not in SECTION_ORDER]
    return [(s, by_section[s]) for s in ordered], len(visible)


def save_purchase(name, selection, items_by_id):
    """Comprueba disponibilidad, registra SIEMPRE primero la compra (quién ha
    comprado qué) y solo después descuenta las unidades. Así, si algo falla a
    medias, nunca desaparece un artículo sin que quede su registro. Devuelve
    (ok, mensaje) y captura cualquier error para mostrarlo en pantalla en vez
    de romper la página."""
    try:
        ss = get_spreadsheet()
        ws_items = ss.worksheet(SHEET_ITEMS)
        ws_purch = ss.worksheet(SHEET_PURCHASES)

        header_row = ws_items.row_values(1)
        if "compradas" not in header_row:
            return False, "Falta la columna 'compradas' en APP_datos. Avisa a Alfredo."
        compradas_col = header_row.index("compradas") + 1

        records = ws_items.get_all_records(numericise_ignore=["all"])
        row_by_id = {}
        for idx, r in enumerate(records, start=2):  # row 1 is the header
            rid = str(r.get("id", "")).strip()
            if rid:
                row_by_id[rid] = (idx, r)

        now = dt.datetime.now().isoformat(timespec="seconds")
        purchase_rows = []
        updates = []

        for item_id, qty in selection.items():
            qty = _to_int(qty, default=0)
            if qty <= 0:
                continue
            if item_id not in row_by_id:
                return False, "Uno de los artículos ya no existe. Recarga la página e inténtalo de nuevo."
            row_idx, record = row_by_id[item_id]
            necesarias = _to_int(record.get("necesarias"), default=1) or 1
            compradas = _to_int(record.get("compradas"), default=0)
            left = necesarias - compradas
            if qty > left:
                nombre = items_by_id.get(item_id, {}).get("nombre", item_id)
                return False, (
                    f"Alguien se te ha adelantado con «{nombre}» hace un momento. "
                    "Recarga la página para ver lo que queda disponible."
                )
            precio = _parse_precio_range(record.get("precio"))
            purchase_rows.append([now, item_id, name, qty, round(qty * precio, 2)])
            updates.append((row_idx, compradas + qty))

        if not purchase_rows:
            return False, "No se ha seleccionado ningún artículo."

        # 1) Lo primero e imprescindible: registrar la compra (quién, qué,
        #    cuánto). Si esto falla, no se toca nada más.
        ws_purch.append_rows(purchase_rows, value_input_option="USER_ENTERED")

        # 2) Ya con la compra a salvo, descontamos las unidades disponibles.
        for row_idx, new_compradas in updates:
            ws_items.update_cell(row_idx, compradas_col, new_compradas)

        load_items.clear()
        return True, "ok"
    except Exception as exc:  # noqa: BLE001 — queremos avisar, no romper
        return False, (
            "No se ha podido guardar en este momento "
            f"({type(exc).__name__}). Espera unos segundos y vuelve a "
            "intentarlo. Si sigue fallando, avisa a Alfredo."
        )


# --------------------------------------------------------------------------
# Interfaz
# --------------------------------------------------------------------------

st.set_page_config(page_title=f"Lista de {BABY_NAME}", page_icon="🎁", layout="centered")

st.markdown(
    """
    <style>
      /* Colores fijos: legibles tanto si el móvil está en claro como en
         oscuro. Forzamos fondo claro y texto oscuro en toda la página. */
      .stApp { background:#F5F6F0; color:#1F2A24; }
      .stApp h1, .stApp h2, .stApp h3, .stApp h4,
      .stApp p, .stApp label, .stApp li { color:#1F2A24; }
      div.block-container { max-width: 640px; padding-top: 2rem; }
      h1 { font-size: 2rem !important; }
      .item-card {
        background:#FFFFFF; border:1px solid #DCE3DA; border-radius:16px;
        padding:16px 18px; margin-bottom:14px; color:#1F2A24;
      }
      .item-card h4 { color:#1F2A24; }
      .item-price { font-size:1.25rem; font-weight:800; color:#1F2A24; }
      .item-pill {
        float:right; background:#EDF0E9; color:#5C6B62; border-radius:999px;
        padding:2px 10px; font-size:0.78rem; font-weight:700;
      }
      /* Botones grandes y cómodos de pulsar, también desde el móvil.
         El ancho completo se fuerza aquí por CSS (en vez de con el antiguo
         use_container_width, que Streamlit ha ido retirando). */
      .stButton > button, .stFormSubmitButton > button {
        width:100%;
        padding:0.7rem 1rem; font-size:1.05rem; font-weight:700;
        border-radius:12px; margin-top:-4px; margin-bottom:6px;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

if "selection" not in st.session_state:
    st.session_state.selection = {}
if "step" not in st.session_state:
    st.session_state.step = "browse"
if "banner" not in st.session_state:
    st.session_state.banner = None

ensure_sheets()
sync_from_source_cached()
items = load_items()
items_by_id = {it["id"]: it for it in items}

st.title(f"Lista de {BABY_NAME}")
st.write(
    f"Estos son los artículos que nos harían mucha ilusión para {BABY_NAME}. "
    "Elige lo que quieras regalarle: en cuanto alguien lo reserva, desaparece "
    "de la lista para que nadie lo repita."
)
st.markdown("#### ¿Cómo funciona?")
st.markdown(
    "1. Marca lo que te apetezca regalar.\n"
    "2. Baja hasta el final y pulsa **Guardar selección**.\n"
    "3. Escribe tu nombre y confirma.\n"
    "4. Haznos un ingreso por el importe al número de cuenta "
    "**ES70 2095 5308 3091 2564 9315**. ¡Y ya está!"
)
st.markdown(
    "Para facilitar la recepción de los artículos en casa y por comodidad, "
    "las compras las haremos nosotros. Os agradecemos muchísimo vuestra "
    "aportación y os prometemos enviaros una foto con lo que nos habéis regalado. 💛"
)

if st.session_state.banner:
    b = st.session_state.banner
    st.success(
        f"¡Gracias, {b['name']}! Hemos guardado tu selección de {b['count']} "
        f"artículo{'s' if b['count'] != 1 else ''} por {b['total']:.2f} €."
    )
    if st.button("Vale, entendido"):
        st.session_state.banner = None
        st.rerun()

def render_item(item):
    """Dibuja la tarjeta de un artículo y su control para regalarlo."""
    left = remaining(item)
    nombre_html = html.escape(item["nombre"])
    # La descripción puede tener varias líneas (p.ej. "Incluye: ...");
    # se escapan y los saltos de línea se convierten en <br>.
    detalle_html = html.escape(item["detalle"]).replace("\n", "<br>")
    necesita = item["necesarias"]
    cantidad_pill = (
        f'<span class="item-pill">Faltan {left} de {necesita}</span>'
        if necesita > 1 else
        f'<span class="item-pill">Falta{"n" if left != 1 else ""} {left}</span>'
    )
    # Se construye el HTML uniendo solo las partes que existen, sin sangría:
    # así, cuando falta la descripción o el enlace, no queda ninguna línea
    # vacía (que Streamlit interpretaría como un bloque de código gris).
    card = ['<div class="item-card">', cantidad_pill,
            f'<h4 style="margin:0 0 2px 0;">{nombre_html}</h4>']
    if item["detalle"]:
        card.append(f'<p style="color:#5C6B62; margin:0 0 8px 0;">{detalle_html}</p>')
    card.append(
        f'<div class="item-price">{item["precio"]:.2f} € '
        '<span style="font-size:0.8rem; font-weight:600; color:#5C6B62;">/ unidad</span></div>'
    )
    if item["link"]:
        card.append(
            f'<a href="{html.escape(item["link"])}" target="_blank">Ver producto ↗</a>'
        )
    card.append("</div>")
    with st.container():
        st.markdown("".join(card), unsafe_allow_html=True)
        iid = item["id"]
        selected = iid in st.session_state.selection
        if necesita > 1:
            # Varias unidades: primero un botón para empezar a regalar; una vez
            # dentro, un selector de cuántas y un botón para quitar.
            if selected:
                qty = st.number_input(
                    f"¿Cuántas unidades regalas? (quedan {left})",
                    min_value=1, max_value=left,
                    value=min(st.session_state.selection.get(iid, 1), left),
                    key=f"qty_{iid}",
                )
                st.session_state.selection[iid] = qty
                if st.button("Quitar", key=f"rm_{iid}"):
                    st.session_state.selection.pop(iid, None)
                    st.rerun()
            else:
                if st.button("🎁 Quiero regalar esto", type="primary",
                             key=f"add_{iid}"):
                    st.session_state.selection[iid] = 1
                    st.rerun()
        else:
            # Una sola unidad: un único botón que alterna seleccionar / quitar.
            if selected:
                if st.button("✓ Vas a regalar esto · pulsa para quitar",
                             key=f"btn_{iid}"):
                    st.session_state.selection.pop(iid, None)
                    st.rerun()
            else:
                if st.button("🎁 Quiero regalar esto", type="primary",
                             key=f"btn_{iid}"):
                    st.session_state.selection[iid] = 1
                    st.rerun()


visible_items = [it for it in items if remaining(it) > 0]

if not visible_items:
    st.info(f"¡Ya está todo reservado! Gracias a todos, no queda ningún artículo pendiente para {BABY_NAME}.")
else:
    opciones_orden = ["Por sección", "Más baratos primero", "Más caros primero"]
    if hasattr(st, "segmented_control"):
        orden = st.segmented_control(
            "Ordenar", opciones_orden, default="Por sección",
            key="orden", label_visibility="collapsed",
        ) or "Por sección"
    else:
        orden = st.radio(
            "Ordenar", opciones_orden, horizontal=True,
            key="orden", label_visibility="collapsed",
        )

    if orden == "Por sección":
        groups, _ = group_by_section(items)
        for seccion, section_items in groups:
            st.subheader(seccion)
            for item in section_items:
                render_item(item)
    else:
        reverse = orden == "Más caros primero"
        for item in sorted(visible_items, key=lambda it: it["precio"], reverse=reverse):
            render_item(item)

selection = {k: v for k, v in st.session_state.selection.items() if v > 0}
sel_count = sum(selection.values())
sel_total = sum(items_by_id[i]["precio"] * q for i, q in selection.items() if i in items_by_id)

st.divider()

if sel_count > 0:
    col1, col2 = st.columns([2, 1])
    with col1:
        st.metric("Seleccionado", f"{sel_count} artículo{'s' if sel_count != 1 else ''}", f"{sel_total:.2f} €")
    with col2:
        if st.button("Guardar selección", type="primary"):
            st.session_state.step = "confirm"
            st.rerun()

if st.session_state.step == "confirm" and sel_count > 0:
    with st.form("confirm_form"):
        st.subheader("Confirma tu selección")
        for item_id, qty in selection.items():
            it = items_by_id.get(item_id)
            if not it:
                continue
            label = it["nombre"] + (f" × {qty}" if qty > 1 else "")
            st.write(f"- {label} — {it['precio'] * qty:.2f} €")
        st.write(f"**Total: {sel_total:.2f} €**")
        name = st.text_input("Tu nombre", placeholder="Por ejemplo: Tía Rosa")
        c1, c2 = st.columns(2)
        cancel = c1.form_submit_button("Cancelar")
        confirm = c2.form_submit_button("Confirmar y guardar", type="primary")

        if cancel:
            st.session_state.step = "browse"
            st.rerun()

        if confirm:
            clean_name = name.strip()
            if not clean_name:
                st.error("Escribe tu nombre para poder guardar la selección.")
            else:
                ok, msg = save_purchase(clean_name, selection, items_by_id)
                if ok:
                    st.session_state.banner = {"name": clean_name, "count": sel_count, "total": sel_total}
                    st.session_state.selection = {}
                    st.session_state.step = "browse"
                    st.rerun()
                else:
                    st.error(msg)
