# Lista de Martín

Web pública (sin cuenta ni inicio de sesión para quien la visita) que lee y
guarda las selecciones directamente en tu Google Sheet "Compras Martín",
usando una cuenta de servicio de Google — el mismo patrón que la Mundoporra.

Tú solo editas **`Hoja 1`** (tu hoja de trabajo de siempre, con todo lo que
necesitáis para Martín, incluidas cosas internas como botiquín o pañales que
no queréis pedir a la familia). La web crea y mantiene sola, a partir de ahí,
dos pestañas más:
- `APP_datos`: solo los artículos marcados como públicos, con sus unidades
  necesarias/compradas. **No la edites a mano** — se regenera sola cada vez
  que alguien abre la web, leyendo `Hoja 1`. Cualquier cambio manual que
  hagas ahí se puede sobrescribir en la siguiente sincronización.
- `APP_compras`: el registro de quién ha comprado qué (solo lo veis tú y tu
  pareja, abriendo el Sheet — la web pública nunca lo muestra).

## 1. Crear la cuenta de servicio de Google (una sola vez)

1. Ve a https://console.cloud.google.com/ e inicia sesión con tu cuenta de Google.
2. Arriba a la izquierda, crea un proyecto nuevo (o usa uno existente). Nómbralo, por ejemplo, `lista-martin`.
3. En el buscador superior escribe **"Google Sheets API"**, ábrela y pulsa **Habilitar**.
4. En el menú lateral: **IAM y administración** → **Cuentas de servicio** → **Crear cuenta de servicio**.
   - Nombre: `lista-martin`.
   - Pulsa **Crear y continuar**, luego **Listo** (no hace falta darle ningún rol de proyecto).
5. Entra en la cuenta de servicio que acabas de crear → pestaña **Claves** → **Agregar clave** → **Crear clave nueva** → tipo **JSON**.
   - Se descargará un archivo `.json`. Guárdalo, lo necesitarás en el paso 3.
6. Copia el **email** de la cuenta de servicio (algo como `lista-martin@tu-proyecto.iam.gserviceaccount.com`, aparece en la lista de cuentas de servicio).

## 2. Compartir tu Google Sheet con la cuenta de servicio

1. Abre tu Sheet "Compras Martín".
2. Botón **Compartir** → pega el email de la cuenta de servicio (paso 1.6) → dale permiso de **Editor** → Enviar.

Sin este paso la web no podrá leer ni escribir nada.

## 3. Subir el código a GitHub

Este repositorio ya contiene todo el código (`app.py`, `requirements.txt`).
Si Claude te ha ayudado a crear el repo, este paso ya está hecho.

## 4. Desplegar en Streamlit Community Cloud

1. Ve a https://share.streamlit.io/ e inicia sesión con GitHub.
2. **New app** → elige el repositorio → archivo principal `app.py`.
3. Antes de desplegar (o justo después, en **Settings → Secrets**), pega el
   contenido de `.streamlit/secrets.toml.example`, pero con tus valores
   reales:
   - `spreadsheet_id`: el ID de tu Sheet (la parte de la URL entre
     `/d/` y `/edit`).
   - Los campos de `[gcp_service_account]`: cópialos directamente del
     archivo `.json` que descargaste en el paso 1.5 (cada campo del JSON
     tiene el mismo nombre que aquí).
   - **Importante**: en `private_key`, mantén las `\n` tal cual aparecen en
     el JSON (no las borres ni las conviertas en saltos de línea reales).
4. Guarda los secretos y despliega. Streamlit te da una URL pública
   (algo como `https://lista-martin.streamlit.app`) — ese es el enlace que
   compartes por WhatsApp con la familia. Nadie necesita cuenta de nada
   para abrirlo, verlo ni guardar su selección.

## Cómo consultar quién ha comprado qué

Abre tu Google Sheet normal y ve a la pestaña `APP_compras`. Ahí verás
fecha, artículo, nombre de quien lo compró, cantidad e importe — información
que la web pública nunca muestra.

## Cómo decidir qué aparece en la lista pública

Todo pasa por `Hoja 1`, tu hoja de siempre (columnas SECCIÓN, ELEMENTO,
SUB-ELEMENTO, COMENTARIOS, LINK PRODUCTO, PRECIO, QUIÉN).

1. Añade una columna nueva con la cabecera **`EN_LISTA`** (en cualquier
   posición; el nombre de la cabecera es lo único que importa, no el orden).
2. En esa columna, escribe **`sí`** en las filas que quieres que vea la
   familia (cuna, hamaca, silla del coche...) y **`no`**, o déjala en blanco,
   en las que son solo para vosotros (botiquín, pañales...).
3. Para que una fila aparezca en la web hace falta además que tenga
   **ELEMENTO**, **LINK PRODUCTO** y **PRECIO** rellenos — si falta alguno,
   la fila se ignora hasta que la completes, aunque pongas `sí`.
4. Si en COMENTARIOS o en SUB-ELEMENTO escribes algo como `x2` o `x3`, la web
   entiende que hacen falta 2 o 3 unidades de ese artículo (por ejemplo,
   "sábanas x2"). Si no pones nada, asume que hace falta 1.
5. Si el PRECIO es un rango (por ejemplo `885 - 935`), la web se queda con el
   primer número.

Cada vez que alguien abre la web, esta relee `Hoja 1`, actualiza `APP_datos`
automáticamente (como mucho una vez cada 30 segundos) y refleja los cambios
— nunca hace falta tocar `APP_datos` a mano. Las unidades ya compradas
(`compradas`) nunca se pierden ni se reinician al sincronizar, aunque
cambies el precio, el nombre o quites y vuelvas a poner el `sí`.

Si quitas el `sí` de una fila que ya tenía compras, esa fila se oculta de la
web pero no se borra de `APP_datos`, así que el historial de quién la compró
sigue intacto en `APP_compras`.
