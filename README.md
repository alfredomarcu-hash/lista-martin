# Lista de Martín

Web pública (sin cuenta ni inicio de sesión para quien la visita) que lee y
guarda las selecciones directamente en tu Google Sheet "Compras Martín",
usando una cuenta de servicio de Google — el mismo patrón que la Mundoporra.

La web crea automáticamente, la primera vez que arranca, dos pestañas nuevas
en tu Sheet:
- `APP_datos`: los artículos, con sus unidades necesarias/compradas.
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

## Actualizar la lista de artículos

Edita directamente la pestaña `APP_datos` de tu Sheet (añadir filas, cambiar
precios, etc.). La web las recoge solas, con un pequeño retraso de hasta 8
segundos.
