"""
Lista de Martín — lista de regalos para el bebé, sin necesidad de cuenta
para quien la visita. Lee y escribe directamente en un Google Sheet
mediante una cuenta de servicio (igual que la Mundoporra).
"""

import datetime as dt

import gspread
import streamlit as st
from google.oauth2.service_account import Credentials

# --------------------------------------------------------------------------
# Configuración
# --------------------------------------------------------------------------

BABY_NAME = "Martín"

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

SHEET_ITEMS = "APP_datos"
SHEET_PURCHASES = "APP_compras"

ITEMS_HEADER = [
    "id", "seccion", "nombre", "detalle", "link", "precio", "necesarias", "compradas",
]
PURCHASES_HEADER = ["fecha", "item_id", "nombre_comprador", "cantidad", "importe"]

SECTION_ORDER = ["Dormitorio", "Baño", "Salón", "Coche", "Paseo", "Textil", "Lactancia"]

# Semilla inicial: se usa solo la primera vez, si la pestaña APP_datos no existe.
SEED_ITEMS = [
    ["minicuna", "Dormitorio", "Minicuna Jané", "Colchón, funda nórdica y cojín incluidos",
     "https://janeworld.com/cunas-colecho/801993-103052-cuna-colecho-baby-side.html#/761424-color-botanic",
     199, 1, 0],
    ["saco-dormir", "Dormitorio", "Saco de dormir TOG 2.5", "Molis&Co, con mangas, ideal para invierno",
     "https://molisandco.com/products/saco-de-dormir-bebe-con-mangas-winter-animals-tog-2-5",
     37, 2, 0],
    ["almohada-antiplagio", "Dormitorio", "Almohada antiplagiocefalia", "Por si hiciera falta más adelante",
     "https://koalababycare.com/es/collections/newborn-pillows",
     30, 1, 0],
    ["banera", "Baño", "Bañera con patas y soporte", "Stokke Flexibath, pack completo",
     "https://www.stokke.com/ESP/es-es/bano/stokke-flexibath/flexibath-newborn-stand-bundle.html?5319_0=pid%3D531910%26color%3D561",
     119, 1, 0],
    ["hamaca", "Salón", "Hamaca BabyBjörn Bliss", "Tejido 3D Jersey, beige claro",
     "https://www.babybjorn.es/productos/hamacas/hamaca-bliss/beige-claro-jersey-3d-gris-claro/",
     229, 1, 0],
    ["trona", "Salón", "Trona Stokke Tripp Trapp", "Pack recién nacido completo",
     "https://www.stokke.com/ESP/es-es/tronas/tripp-trapp/tripp-trapp-newborn-complete.html",
     379, 1, 0],
    ["sillita-coche", "Coche", "Silla de coche BeSafe Beyond", "Presupuesto de Cucuna (Terrassa), desde 885 €",
     "https://www.besafe.com/es/asientos-de-coche/recien-nacidos-y-bebes/beyond-2-360-b/",
     885, 1, 0],
    ["carro", "Paseo", "Carro Inglesina Aptica", "Sistema 2 en 1, con base para casa",
     "https://www.inglesina.com/es-es/products/carritos-bebe-3-piezas-aptica-duo?srsltid=AfmBOorUIDMpu4ah5aZHDSEOUNXnGFE7W_IYfPoOYaJPmad_9U2cZSC5&variant=57481760178560",
     949, 1, 0],
    ["mochila-porteo", "Paseo", "Mochila de porteo Ergobaby", "Omni Deluxe, algodón, color Pearl Grey",
     "https://ergobaby.com/es-es/products/mochila-portabebes-omni-deluxe?variant=51332179984672",
     198, 1, 0],
    ["manta", "Textil", "Manta de punto 100% algodón", "Zara Home",
     "https://www.zarahome.com/es/manta-bebe-punto-l43699004?ct=true&categoryId=1020569688&pelement=507772437&colorId=999",
     29.90, 1, 0],
    ["muselinas", "Textil", "Pack de muselinas 100% algodón", "55x55 cm, Zara Home. Hacen falta 2 packs",
     "https://www.zarahome.com/es/pack-muselinas-bebe-multicolor-pack-de-3-l41601767?srch=true&searchTerm=muselina&pelement=507776346&colorId=500",
     9.99, 2, 0],
    ["tetinas", "Lactancia", "Tetinas Philips Avent", "Natural Response, flujo 1, pack de 2",
     "https://www.amazon.es/dp/B0BWFMMPPC/?coliid=I2D6GVD0B0H2XC&colid=1EPKH89AFHP94&ref_=list_c_wl_lv_ov_lig_dp_it&th=1",
     6.99, 1, 0],
    ["bolsas-esterilizar", "Lactancia", "Bolsas para esterilizar al microondas", "Philips Avent, 20 usos por bolsa",
     "https://www.amazon.es/dp/B00DUEFZK8/?coliid=I3LJUT4PTFHWOV&colid=1EPKH89AFHP94&ref_=list_c_wl_lv_ov_lig_dp_it&th=1",
     12.5, 1, 0],
]

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
        ws.update("A1", [ITEMS_HEADER] + SEED_ITEMS)

    if SHEET_PURCHASES not in titles:
        ws = ss.add_worksheet(title=SHEET_PURCHASES, rows=500, cols=len(PURCHASES_HEADER))
        ws.update("A1", [PURCHASES_HEADER])


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
    rows = ws.get_all_records()
    items = []
    for r in rows:
        item_id = str(r.get("id", "")).strip()
        if not item_id:
            continue  # a blank row, or one still missing its id
        if not _is_visible(r):
            continue  # marked as internal-only (en_lista != sí)

        precio = _to_float(r.get("precio"))
        link = str(r.get("link", "")).strip()
        necesarias = _to_int(r.get("necesarias"), default=1) or 1

        if precio <= 0 or not link:
            continue  # not ready to be reserved yet (no precio/link todavía)

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
    """Re-reads the sheet, checks availability again, writes the purchase
    and updates the counters. Returns (ok, message)."""
    ss = get_spreadsheet()
    ws_items = ss.worksheet(SHEET_ITEMS)
    ws_purch = ss.worksheet(SHEET_PURCHASES)

    header_row = ws_items.row_values(1)
    if "compradas" not in header_row:
        return False, "Falta la columna 'compradas' en APP_datos. Avisa a Alfredo."
    compradas_col = header_row.index("compradas") + 1

    records = ws_items.get_all_records()
    row_by_id = {}
    for idx, r in enumerate(records, start=2):  # row 1 is the header
        rid = str(r.get("id", "")).strip()
        if rid:
            row_by_id[rid] = (idx, r)

    now = dt.datetime.now().isoformat(timespec="seconds")
    purchase_rows = []
    updates = []

    for item_id, qty in selection.items():
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
        precio = _to_float(record.get("precio"))
        purchase_rows.append([now, item_id, name, qty, round(qty * precio, 2)])
        updates.append((row_idx, compradas + qty))

    if not purchase_rows:
        return False, "No se ha seleccionado ningún artículo."

    for row_idx, new_compradas in updates:
        ws_items.update_cell(row_idx, compradas_col, new_compradas)

    ws_purch.append_rows(purchase_rows)

    load_items.clear()
    return True, "ok"


# --------------------------------------------------------------------------
# Interfaz
# --------------------------------------------------------------------------

st.set_page_config(page_title=f"Lista de {BABY_NAME}", page_icon="🎁", layout="centered")

st.markdown(
    """
    <style>
      .stApp { background:#F5F6F0; }
      div.block-container { max-width: 640px; padding-top: 2rem; }
      h1 { font-size: 2rem !important; }
      .item-card {
        background:#FFFFFF; border:1px solid #DCE3DA; border-radius:16px;
        padding:16px 18px; margin-bottom:14px;
      }
      .item-price { font-size:1.25rem; font-weight:800; }
      .item-badge {
        display:inline-block; font-size:0.75rem; font-weight:700;
        color:#5C6B62; margin-bottom:4px;
      }
      .item-pill {
        float:right; background:#EDF0E9; color:#5C6B62; border-radius:999px;
        padding:2px 10px; font-size:0.78rem; font-weight:700;
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
items = load_items()
items_by_id = {it["id"]: it for it in items}

st.title(f"Lista de {BABY_NAME}")
st.write(
    f"Estos son los artículos que nos harían mucha ilusión para {BABY_NAME}. "
    "Elige lo que quieras regalarle: en cuanto alguien lo reserva, desaparece "
    "de la lista para que nadie lo repita."
)
with st.expander("¿Cómo funciona?", expanded=False):
    st.markdown(
        "1. Marca lo que te apetezca regalar.\n"
        "2. Baja hasta el final y pulsa **Guardar selección**.\n"
        "3. Escribe tu nombre y confirma. ¡Y ya está!"
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

groups, total_visible = group_by_section(items)

if total_visible == 0:
    st.info(f"¡Ya está todo reservado! Gracias a todos, no queda ningún artículo pendiente para {BABY_NAME}.")
else:
    for seccion, section_items in groups:
        st.subheader(seccion)
        for item in section_items:
            left = remaining(item)
            with st.container():
                st.markdown(
                    f"""<div class="item-card">
                    <span class="item-badge">{seccion}</span>
                    <span class="item-pill">Falta{'n' if left != 1 else ''} {left}</span>
                    <h4 style="margin:4px 0 2px 0;">{item['nombre']}</h4>
                    <p style="color:#5C6B62; margin:0 0 8px 0;">{item['detalle']}</p>
                    <div class="item-price">{item['precio']:.2f} € <span style="font-size:0.8rem; font-weight:600; color:#5C6B62;">/ unidad</span></div>
                    <a href="{item['link']}" target="_blank">Ver producto ↗</a>
                    </div>""",
                    unsafe_allow_html=True,
                )
                if item["necesarias"] > 1:
                    qty = st.number_input(
                        "Cuántos quieres regalar",
                        min_value=0, max_value=left, value=st.session_state.selection.get(item["id"], 0),
                        key=f"qty_{item['id']}", label_visibility="collapsed",
                    )
                    if qty > 0:
                        st.session_state.selection[item["id"]] = qty
                    else:
                        st.session_state.selection.pop(item["id"], None)
                else:
                    checked = st.checkbox(
                        "Quiero regalar esto", value=item["id"] in st.session_state.selection,
                        key=f"chk_{item['id']}",
                    )
                    if checked:
                        st.session_state.selection[item["id"]] = 1
                    else:
                        st.session_state.selection.pop(item["id"], None)

selection = {k: v for k, v in st.session_state.selection.items() if v > 0}
sel_count = sum(selection.values())
sel_total = sum(items_by_id[i]["precio"] * q for i, q in selection.items() if i in items_by_id)

st.divider()

if sel_count > 0:
    col1, col2 = st.columns([2, 1])
    with col1:
        st.metric("Seleccionado", f"{sel_count} artículo{'s' if sel_count != 1 else ''}", f"{sel_total:.2f} €")
    with col2:
        if st.button("Guardar selección", type="primary", use_container_width=True):
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
        cancel = c1.form_submit_button("Cancelar", use_container_width=True)
        confirm = c2.form_submit_button("Confirmar y guardar", type="primary", use_container_width=True)

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
