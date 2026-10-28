# InstaFlow ⚡ — Dashboard Profesional de Scraping y Análisis de Instagram

**InstaFlow** es una aplicación integral, modular y profesional desarrollada en **Python (Flask)** y **Selenium**, diseñada para la extracción, visualización y análisis de perfiles y publicaciones públicas o autorizadas de Instagram. Su interfaz de usuario moderna, oscura y reactiva está inspirada en la experiencia visual de **n8n**.

---

## 🚀 Características Principales

- **Diseño visual inspirado en n8n:**
  - Lienzo oscuro (`#0b0c13`), tarjetas modulares con bordes sutiles y acentos violetas (`#8936FF`), azules (`#3F8CFF`) y esmeralda (`#00C49F`).
  - Pipeline interactivo que desglosa en tiempo real las **16 etapas** de la extracción con duraciones y estados.
  - Consola terminal en vivo para registrar eventos de red y progreso.
  - Tarjetas de métricas independientes que distinguen rigurosamente entre valores reales (incluido el `0`) y datos desconocidos (`No disponible`), sin inventar datos.
- **Galería de publicaciones interactiva:**
  - Tarjetas cuadradas con miniaturas reales en alta resolución extraídas del atributo `srcset`.
  - Detección diferenciada de tipos de contenido: **Fotografía**, **Carrusel multi-imagen**, **Vídeo** y **Reel**.
  - Filtros instantáneos por tipo de medio, buscador por texto en pie de foto y lightbox modal para zoom de imágenes.
  - Paginación progresiva para garantizar rendimiento fluido sin saturar la memoria del navegador.
- **Gestión de imágenes y medios:**
  - Descarga de imágenes únicamente desde dominios autorizados de Meta (`cdninstagram.com`, `fbcdn.net`) con protección contra SSRF.
  - Validación de integridad con **Pillow** (`Image.verify()`), conversión a JPEG optimizado y asignación de nombres únicos con hashes SHA-256.
  - Generación opcional de captura de pantalla en PNG del encabezado del perfil analizado.
- **Arquitectura asíncrona sin bloqueos:**
  - Gestor de trabajos en segundo plano (`JobManager`) basado en hilos (`threading`), con identificadores únicos UUIDv4.
  - El hilo principal de Flask nunca se congela; el frontend sondea el progreso mediante la API REST (`/api/jobs/<job_id>`).
  - Soporte de cancelación segura cooperativa en cualquier etapa de la extracción.
- **Persistencia y exportación multiformato:**
  - Almacenamiento completo de cada ejecución en archivos **JSON** UTF-8 (`data/results/`).
  - Exportación tabular a **CSV** mediante **Pandas**, con codificación UTF-8 con BOM (`utf-8-sig`) para compatibilidad directa con Microsoft Excel en Windows (conservando tildes y emojis).
  - Base de datos relacional **SQLite** (`data/database/instaflow.db`) para registro histórico de ejecuciones, perfiles y publicaciones.
- **Cumplimiento ético y seguridad:**
  - Uso exclusivo de métodos autorizados y navegación estándar de Chrome mediante Selenium Manager.
  - Sin elusión de CAPTCHA, sin bypass de 2FA y sin evasión de restricciones.
  - Cookies y API keys centralizadas en la carpeta `env/`, excluida de Git.

---

## 🛠️ Tecnologías Utilizadas

| Componente | Tecnología | Propósito |
| :--- | :--- | :--- |
| **Backend / API** | Python 3.11+ / Flask 3.1+ | Servidor web local y API REST asíncrona |
| **Automatización** | Selenium 4.20+ / Selenium Manager | Control de Google Chrome y navegación DOM |
| **Datos / Exportación** | Pandas 2.2+ | Generación de reportes tabulares y CSV |
| **Validación de Imagen**| Pillow 10.3+ | Verificación de integridad y optimización de medios |
| **Parser HTML** | BeautifulSoup4 | Extracción de metadatos Open Graph y JSON-LD |
| **Persistencia** | SQLite 3 / JSON / CSV | Almacenamiento histórico y caché local |
| **Frontend** | HTML5 / CSS3 / Vanilla JavaScript | Dashboard n8n-style sin dependencias pesadas |
| **Pruebas** | pytest 8.0+ | Pruebas unitarias automatizadas |

---

## 📁 Estructura del Proyecto

```text
instagram-dashboard/
├── app.py                     # Servidor Flask y endpoints de la API REST
├── config.py                  # Configuración centralizada de la aplicación
├── requirements.txt           # Dependencias de Python fijadas
├── README.md                  # Manual completo de instalación y uso
├── bigfive_analyzer.py        # Análisis de personalidad Big Five (OCEAN) con Google Gemini
├── .gitignore                 # Exclusiones de Git (secretos de env/, data/, media/, screenshots/)
├── env/                       # Archivos sensibles: en Git solo van las plantillas *.example
│   ├── cookies.example.json   # Plantilla de cookies (se sube a Git)
│   ├── api_key.example.txt    # Plantilla de la API key (se sube a Git)
│   ├── cookies.json           # Cookies reales de sesión (local, NO se sube)
│   └── api_key.txt            # API key de Google Gemini (local, NO se sube)
├── scraper/
│   ├── __init__.py
│   ├── browser.py             # Controlador Selenium y gestión de Chrome
│   ├── session_manager.py     # Manejo de sesión y cookies autorizadas
│   ├── profile_extractor.py   # Extracción multiescalonada de perfil (OG, DOM, JSON-LD)
│   ├── post_extractor.py      # Extracción de cuadrícula, srcset y tipos de medio
│   ├── image_downloader.py    # Descarga segura y validación Pillow
│   ├── scraper_service.py     # Orquestador de las 16 etapas de extracción
│   ├── job_manager.py         # Administrador de tareas en segundo plano
│   ├── audience_extractor.py  # Seguidores/Seguidos + alternancia MODE (clase aparte)
│   ├── benford_analysis.py    # Ley de Benford: primer dígito, chi-cuadrado, clasificación
│   ├── validators.py          # Validadores de username, contadores y sanitización
│   └── exceptions.py          # Excepciones estructuradas del sistema
├── storage/
│   ├── __init__.py
│   ├── json_storage.py        # Almacenamiento y carga de resultados JSON
│   ├── csv_storage.py         # Exportación tabular con Pandas (UTF-8 BOM)
│   └── database.py            # Gestor de base de datos SQLite histórica
├── templates/
│   ├── index.html             # Vista principal del Dashboard (incluye el modal BIG FIVE)
│   ├── profile.html           # Vista detallada de perfil almacenado
│   ├── audience.html          # Seguidores/Seguidos + dashboard de la Ley de Benford
│   └── settings.html          # Panel de diagnóstico y configuración
├── static/
│   ├── css/
│   │   ├── dashboard.css      # Sistema de diseño n8n (variables, layout, timeline)
│   │   ├── gallery.css        # Estilos de la cuadrícula de publicaciones y tarjetas
│   │   └── audience.css       # Tabla de audiencia, tarjeta hover y dashboard de Benford
│   ├── js/
│   │   ├── api.js             # Cliente HTTP REST asíncrono
│   │   ├── dashboard.js       # Controlador de eventos, métricas y sondeo de tareas
│   │   ├── gallery.js         # Filtros, búsqueda, lightbox y paginación
│   │   └── audience.js        # Sondeo de audiencia, tabla, hover card y gráfico de Benford
│   └── img/
│       └── placeholder.svg    # Imagen de respaldo con gradiente oscuro
├── data/                      # (se crea al ejecutar; excluida de Git)
│   ├── results/               # Resultados exportados en JSON y CSV
│   └── database/              # Archivo de base de datos instaflow.db
├── media/                     # (se crea al ejecutar; excluida de Git)
│   ├── profiles/              # Fotos de perfil descargadas
│   ├── posts/                 # Miniaturas e imágenes de publicaciones
│   └── audience/              # Avatares del listado de seguidores/seguidos
├── screenshots/               # Capturas de perfiles y diagnóstico (excluida de Git)
└── tests/
    ├── test_validators.py     # Pruebas de validación y contadores
    ├── test_profile_extractor.py # Pruebas de extracción de perfiles
    ├── test_post_extractor.py # Pruebas de cuadrícula y tipos de medios
    ├── test_storage.py        # Pruebas de persistencia JSON, CSV y SQLite
    ├── test_benford_analysis.py # Pruebas de la Ley de Benford (dígitos, chi-cuadrado, clasificación)
    └── test_api_endpoints.py  # Pruebas de endpoints Flask
```

---

## 💻 Instalación y Ejecución en Windows

### Requisitos previos
1. **Python 3.11 o superior** instalado y agregado al PATH de Windows.
2. **Google Chrome** instalado en su ruta estándar (`C:\Program Files\Google\Chrome\Application\chrome.exe`).
3. PowerShell de Windows.

### Paso 1: Abrir PowerShell y ubicarse en el proyecto
```powershell
cd C:\Users\ASUS\.gemini\antigravity\scratch\instagram-dashboard
```

### Paso 2: Crear el entorno virtual
```powershell
python -m venv .venv
```

### Paso 3: Activar el entorno virtual
Si PowerShell muestra un error de directiva de ejecución (`ExecutionPolicy`), habilite la ejecución para la sesión actual mediante:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### Paso 4: Instalar las dependencias
```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Paso 5: Iniciar la aplicación
```powershell
python app.py
```

### Paso 6: Abrir el dashboard en su navegador
Una vez iniciado, acceda a:
👉 **[http://127.0.0.1:5000](http://127.0.0.1:5000)**

---

## 🔑 Configuración de Sesión y Cookies Autorizadas

Para consultar cuentas accesibles mediante su sesión autorizada sin introducir contraseñas en la aplicación:

1. Inicie sesión en Instagram desde su navegador habitual (Google Chrome o Firefox).
2. Abra las Herramientas de Desarrollador (**F12**) y diríjase a la pestaña **Application** (o **Almacenamiento** en Firefox) -> **Cookies** -> `https://www.instagram.com`.
3. Copie las cookies principales de sesión: `sessionid`, `ds_user_id` y `csrftoken`.
4. Copie el archivo de ejemplo `env/cookies.example.json` como `env/cookies.json`:
   ```powershell
   Copy-Item env\cookies.example.json env\cookies.json
   ```
5. Edite `env/cookies.json` colocando sus valores reales:
   ```json
   [
     {
       "name": "sessionid",
       "value": "su_valor_sessionid_aqui",
       "domain": ".instagram.com",
       "path": "/",
       "secure": true,
       "httpOnly": true
     },
     {
       "name": "ds_user_id",
       "value": "su_id_de_usuario_aqui",
       "domain": ".instagram.com",
       "path": "/",
       "secure": true,
       "httpOnly": false
     },
     {
       "name": "csrftoken",
       "value": "su_csrftoken_aqui",
       "domain": ".instagram.com",
       "path": "/",
       "secure": true,
       "httpOnly": false
     }
   ]
   ```
6. Al reiniciar o refrescar la aplicación, el badge de sesión en la cabecera mostrará **«Cookies Configuradas»**.
7. Si no desea configurar cookies, la extracción de perfiles y publicaciones funcionará en **Modo Público**. El **análisis de audiencia / Ley de Benford sí exige sesión** (ver más abajo).

> [!IMPORTANT]
> El `sessionid` caduca (al cerrar sesión, cambiar la contraseña o tras un tiempo). Si caduca,
> Instagram lo elimina del navegador y la etapa 3 del análisis de audiencia se detiene con el
> mensaje **«Sesión caducada»**. Basta con volver a copiar las tres cookies en `env/cookies.json`.

> [!NOTE]
> En `.gitignore` se excluye todo `env/` salvo las plantillas `env/cookies.example.json` y
> `env/api_key.example.txt`, para que sus credenciales nunca se suban a un repositorio.

---

## ⚙️ Configuración Centralizada (`config.py`)

Todas las opciones del sistema están centralizadas y documentadas en `config.py`:

- `HEADLESS`: `True` para ejecutar Chrome de fondo sin ventana visible; `False` para ver la ventana de Chrome durante la ejecución.
- `PAGE_LOAD_TIMEOUT`: Tiempo máximo de carga de páginas (30 segundos).
- `ELEMENT_TIMEOUT`: Tiempo de espera explícita `WebDriverWait` (12 segundos).
- `DEFAULT_POSTS_LIMIT`: Cantidad de publicaciones predeterminada (12).
- `MAX_POSTS_LIMIT`: Límite máximo configurable de publicaciones (100).
- `MAX_SCROLL_ATTEMPTS`: Límite de desplazamientos para prevenir bucles infinitos (15).
- `DOWNLOAD_IMAGES`: Habilitar/deshabilitar la descarga local de imágenes en disco.
- `CAPTURE_SCREENSHOT`: Habilitar/deshabilitar la captura PNG del perfil.
- `MAX_CONCURRENT_JOBS`: Límite de tareas simultáneas (2).

---

## 🔄 Las 16 Etapas del Pipeline de Scraping

Cada ejecución se ejecuta a través de 16 etapas sincronizadas y cronometradas en tiempo real:

1. **Validar el nombre de usuario:** Normalización y validación sintáctica de la entrada.
2. **Inicializar Chrome:** Apertura del WebDriver con Selenium Manager y optimizaciones de rendimiento.
3. **Comprobar la sesión y el estado de acceso:** Verificación e inyección de cookies autorizadas.
4. **Abrir el perfil solicitado:** Navegación a la URL oficial del perfil.
5. **Esperar a que el contenido relevante esté disponible:** Espera explícita de hidratación del DOM.
6. **Capturar la información básica:** Nombre completo, biografía con emojis y contadores.
7. **Capturar la fotografía de perfil:** Obtención de URL y descarga local del avatar.
8. **Detectar el número total de publicaciones:** Detección del contador oficial de la cabecera.
9. **Identificar los enlaces de publicaciones:** Detección de nodos `/p/` y `/reel/` en la cuadrícula.
10. **Recopilar los metadatos disponibles:** Clasificación de fotos, carruseles, vídeos y reels.
11. **Obtener las miniaturas:** Selección de la URL de mayor resolución en `srcset`.
12. **Descargar las imágenes autorizadas:** Descarga HTTP segura con gestión de errores por post.
13. **Validar los archivos:** Validación estricta de formato e integridad con Pillow.
14. **Guardar los resultados:** Persistencia simultánea en JSON, CSV y base de datos SQLite.
15. **Actualizar el dashboard:** Transmisión de métricas y estados finales.
16. **Generar un resumen de la ejecución:** Cálculo del tiempo total transcurrido y tasa de éxito.

---

## 🧪 Ejecución de Pruebas Automatizadas

El proyecto incluye una completa suite de pruebas unitarias que no dependen de la red ni de Instagram en vivo:

```powershell
python -m pytest tests -v
```

Resultado verificado:
```text
tests/test_api_endpoints.py::TestAPIEndpoints::test_health_endpoint PASSED
tests/test_api_endpoints.py::TestAPIEndpoints::test_settings_endpoint PASSED
tests/test_api_endpoints.py::TestAPIEndpoints::test_scrape_validation_invalid_username PASSED
tests/test_api_endpoints.py::TestAPIEndpoints::test_scrape_valid_launch PASSED
tests/test_api_endpoints.py::TestAPIEndpoints::test_job_not_found PASSED
tests/test_api_endpoints.py::TestAPIEndpoints::test_cancel_non_existent_job PASSED
tests/test_post_extractor.py::TestPostExtractor::test_parse_single_photo_post PASSED
tests/test_post_extractor.py::TestPostExtractor::test_parse_carousel_post PASSED
tests/test_post_extractor.py::TestPostExtractor::test_parse_reel_post PASSED
tests/test_post_extractor.py::TestPostExtractor::test_extract_best_from_srcset PASSED
tests/test_post_extractor.py::TestPostExtractor::test_clean_caption_accessibility_prefix PASSED
tests/test_profile_extractor.py::TestProfileExtractor::test_extract_from_open_graph_spanish PASSED
tests/test_profile_extractor.py::TestProfileExtractor::test_extract_from_open_graph_english PASSED
tests/test_profile_extractor.py::TestProfileExtractor::test_extract_from_json_ld PASSED
tests/test_profile_extractor.py::TestProfileExtractor::test_detect_profile_not_found PASSED
tests/test_profile_extractor.py::TestProfileExtractor::test_detect_private_account PASSED
tests/test_profile_extractor.py::TestProfileExtractor::test_empty_biography_handling PASSED
tests/test_storage.py::TestStorage::test_json_storage_save_and_load PASSED
tests/test_storage.py::TestStorage::test_csv_storage_profile_and_posts PASSED
tests/test_storage.py::TestStorage::test_sqlite_database_operations PASSED
tests/test_validators.py::TestValidators::test_normalize_username_with_at PASSED
tests/test_validators.py::TestValidators::test_normalize_username_from_url PASSED
tests/test_validators.py::TestValidators::test_validate_username_valid PASSED
tests/test_validators.py::TestValidators::test_validate_username_invalid PASSED
tests/test_validators.py::TestValidators::test_parse_count_string_explicit_zero PASSED
tests/test_validators.py::TestValidators::test_parse_count_string_unknown_or_empty PASSED
tests/test_validators.py::TestValidators::test_parse_count_string_millions PASSED
tests/test_validators.py::TestValidators::test_parse_count_string_thousands PASSED
tests/test_validators.py::TestValidators::test_parse_count_string_formatted_numbers PASSED
tests/test_validators.py::TestValidators::test_sanitize_filename PASSED
tests/test_validators.py::TestValidators::test_is_safe_image_url PASSED

============================= 31 passed in 4.27s ==============================
```

---

## 🧠 Análisis de Personalidad Big Five (Google Gemini)

InstaFlow puede estimar los cinco grandes rasgos de personalidad del modelo **Big Five (OCEAN)** — *Openness, Conscientiousness, Extraversion, Agreeableness, Neuroticism* — a partir de los textos públicos de un perfil ya extraído (biografía, descripciones de publicaciones y demás texto disponible). El análisis lo realiza el modelo de **Google Gemini** mediante una llamada real a su API REST (`bigfive_analyzer.py`).

### La carpeta `env/`

Todos los archivos sensibles se centralizan en `env/`. En Git solo se suben las plantillas:

| Archivo | Contenido | ¿En Git? |
|---|---|---|
| `env/cookies.example.json` | Plantilla de referencia para las cookies | ✅ |
| `env/api_key.example.txt` | Plantilla de referencia para la API key | ✅ |
| `env/cookies.json` | Cookies de sesión de Instagram | ❌ |
| `env/api_key.txt` | API key de Google Gemini | ❌ |

### Configurar la API key

1. Cree una API key de Gemini en [Google AI Studio](https://aistudio.google.com/apikey).
2. Copie la plantilla y pegue la clave, sola y en una línea:
   ```powershell
   Copy-Item env\api_key.example.txt env\api_key.txt
   ```
3. Reinicie la aplicación. La clave nunca se escribe en el código fuente.

### Uso desde el dashboard

1. Primero ejecute una extracción para generar un archivo de resultados en `data/results/` (por ejemplo `usuario_latest.json`).
2. Haga clic en **BIG FIVE** en la barra lateral (justo antes de *Configuración*).
3. En el modal, seleccione el archivo `.json` de resultados y pulse **Analizar**.
4. Mientras Gemini responde se muestra un indicador de carga; después aparecen los cinco rasgos como barras de progreso con su porcentaje (0–100).

### Endpoint

`POST /api/bigfive` — cuerpo `{"profile": <contenido del archivo de resultados>}`. Respuesta:

```json
{
  "status": "success",
  "big_five": {
    "openness": 72.0,
    "conscientiousness": 55.0,
    "extraversion": 68.0,
    "agreeableness": 61.0,
    "neuroticism": 34.0
  }
}
```

Si falta la API key o Gemini falla, devuelve `{"status": "error", "error": "..."}` con un mensaje descriptivo.

> [!NOTE]
> Los puntajes son una estimación automática basada únicamente en texto público; no constituyen una evaluación psicológica profesional. Si el perfil tiene poco texto, el resultado será menos fiable.

---

## 🔢 Análisis de Audiencia (Seguidores/Seguidos) y Ley de Benford

InstaFlow puede extraer el listado de **seguidores o seguidos** (nunca ambos a la vez) de un
perfil objetivo, leer el propio contador de seguidores de cada persona del listado, y aplicar la
**Ley de Benford** sobre el primer dígito significativo de esos contadores para estimar si la
audiencia parece orgánica o inflada con bots.

> [!IMPORTANT]
> **Requiere una sesión válida en `env/cookies.json`.** Sin sesión, Instagram no muestra el
> listado ni deja consultar los contadores de cada perfil (responde 401/429). En ese caso el
> análisis se detiene en la etapa 3 con un mensaje claro, en lugar de terminar con 0 perfiles.

### Cómo se alterna entre "seguidores" y "seguidos"

Es una decisión exclusivamente de código, pensada para que se pueda mostrar en clase: la
constante `AudienceExtractor.MODE`, al principio de `scraper/audience_extractor.py`.

```python
# scraper/audience_extractor.py
class AudienceExtractor:
    MODE = config.AUDIENCE_MODE_FOLLOWING   # <- modo actual: "seguidos"
    # MODE = config.AUDIENCE_MODE_FOLLOWERS # <- cambiar a esto para analizar "seguidores"
```

Cambiar esa única línea redirige automáticamente: la URL del listado que abre Selenium, el
nombre del archivo guardado en `data/results/`, y las etiquetas mostradas en el dashboard. No
hay ningún interruptor en la interfaz web a propósito.

### Cómo se obtienen los datos

1. **Selenium** abre el modal de "Seguidores"/"Seguidos" de Instagram y hace scroll para
   recolectar los nombres de usuario (`AudienceExtractor.collect_usernames`). Esto necesita
   un navegador real porque el modal se arma con JavaScript.
2. **`fetch()` dentro del mismo Chrome** (`AudienceExtractor.enrich_user_profiles`) consulta el
   contador de seguidores de cada username. Se hace desde el navegador (y no con `requests`)
   porque así viaja con la sesión iniciada y la huella real del navegador; Instagram rechaza
   con 429 la misma petición hecha desde fuera. Las consultas van en serie, con una pausa
   (`config.AUDIENCE_REQUEST_DELAY`) entre perfiles:
   - Primero se usa el endpoint JSON `web_profile_info` (datos exactos).
   - Si Instagram lo limita (401/429), el resto del lote lee la **página HTML del perfil** y
     extrae los contadores de su `og:description`. Ahí vienen abreviados (p. ej. «1,2 M»),
     pero el primer dígito, que es lo único que usa Benford, se conserva.
   - Si fallan muchos perfiles seguidos (`config.AUDIENCE_MAX_CONSECUTIVE_FAILURES`), el lote
     se detiene de forma controlada y se analiza lo ya recolectado.

### Cantidad de perfiles a analizar

Se elige desde un selector en la interfaz (`/audience`), entre `config.MIN_AUDIENCE_LIMIT` (200)
y `config.MAX_AUDIENCE_LIMIT` (1000). Es un **máximo**: si la cuenta sigue (o tiene) menos
personas, se analizan todas las disponibles.

> [!NOTE]
> Instagram no siempre lista a todas las cuentas que cuenta. Por ejemplo, un perfil que sigue a
> 74 cuentas puede mostrar solo ~60 en el listado: las cuentas desactivadas, restringidas o que
> han bloqueado a la sesión cuentan en el número, pero no aparecen en el listado.

### La Ley de Benford aplicada (`scraper/benford_analysis.py`)

Por cada persona del listado con un `followers_count` válido, se toma su primer dígito
significativo (1-9) y se compara la distribución observada contra la distribución teórica de
Benford `P(d) = log10(1 + 1/d)`. Con eso se calcula el estadístico chi-cuadrado de bondad de
ajuste (grados de libertad = 8) y se clasifica:

| Clasificación | Condición (umbrales estándar, df=8) |
| :--- | :--- |
| **Humano** | χ² ≤ 15.51 (p > 0.05) |
| **Posible Bot** | 15.51 < χ² ≤ 20.09 (p entre 0.01 y 0.05) |
| **Bot** | χ² > 20.09 (p < 0.01) |
| **Muestra insuficiente** | Menos de `config.BENFORD_MIN_SAMPLE_SIZE` (10) contadores válidos |

El dashboard en `/audience` grafica la curva teórica de Benford superpuesta con las barras de la
distribución observada (con el porcentaje de cada dígito), y muestra el χ², el tamaño de
muestra y el veredicto. Con menos de ~200 perfiles el veredicto es orientativo.

**Ejemplo real** (modo seguidos, n = 59): χ² = 8.28 → **Humano**.

| Dígito | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |
|---|---|---|---|---|---|---|---|---|---|
| Observado | 33.9% | 13.6% | 11.9% | 3.4% | 6.8% | 5.1% | 11.9% | 6.8% | 6.8% |
| Benford | 30.1% | 17.6% | 12.5% | 9.7% | 7.9% | 6.7% | 5.8% | 5.1% | 4.6% |

### Endpoints

- `POST /api/audience/scrape` — body `{"username": "...", "limit": 200, "download_images": true}`.
  Responde `202` con un `job_id` que se consulta como cualquier otro trabajo en
  `GET /api/jobs/<job_id>` (incluye `audience_users` y `benford` cuando termina).
- `GET /api/audience/<username>` — último resultado guardado para ese usuario en el modo actual.

> [!NOTE]
> Visitar entre 200 y 1000 perfiles individuales es, por su naturaleza, una operación larga y
> sensible a los límites de tasa de Instagram. El código aísla fallos por persona y se detiene
> de forma segura ante un patrón de bloqueo, pero no puede garantizar completar un lote grande
> si Instagram decide limitar la sesión.

---

## ⚠️ Limitaciones Conocidas y Uso Ético

1. **Límites de acceso y tasa (Rate Limits):** Instagram aplica límites de frecuencia de solicitudes. Se recomienda espaciar las extracciones consecutivas y utilizar límites moderados de publicaciones (ej. 12 a 50 publicaciones).
2. **Cuentas privadas:** Si una cuenta es privada y la sesión configurada no la sigue con aprobación previa, Instagram no expondrá sus publicaciones; la aplicación detectará el estado privado y concluirá la etapa informándolo claramente.
3. **Persistencia de URLs de CDN:** Las URLs de imágenes en CDN de Instagram contienen firmas con tiempo de expiración. InstaFlow descarga y valida localmente las imágenes para garantizar que permanezcan accesibles permanentemente en el dashboard.
4. **Uso autorizado:** Esta herramienta ha sido diseñada para análisis de cuentas propias, investigación autorizada y auditoría de perfiles accesibles legítimamente. No debe ser utilizada con fines abusivos ni para eludir medidas de seguridad de la plataforma.
