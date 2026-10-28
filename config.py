"""
InstaFlow - Centralized Configuration Module
===========================================
Todas las variables editables y parámetros del sistema se concentran aquí.
No se utilizan variables de entorno ni archivos .env.
"""

from pathlib import Path

# ==============================================================================
# 1. RUTAS BASE DEL SISTEMA DE ARCHIVOS
# ==============================================================================
# Directorio raíz del proyecto
BASE_DIR: Path = Path(__file__).resolve().parent

# Carpeta de configuración sensible (cookies, API keys)
ENV_DIR: Path = BASE_DIR / "env"
ENV_DIR.mkdir(parents=True, exist_ok=True)

# Carpetas de almacenamiento de medios
MEDIA_DIR: Path = BASE_DIR / "media"
PROFILES_MEDIA_DIR: Path = MEDIA_DIR / "profiles"
POSTS_MEDIA_DIR: Path = MEDIA_DIR / "posts"

# Carpeta de capturas de pantalla de perfiles
SCREENSHOTS_DIR: Path = BASE_DIR / "screenshots"

# Carpetas de datos y base de datos
DATA_DIR: Path = BASE_DIR / "data"
RESULTS_DIR: Path = DATA_DIR / "results"
DATABASE_DIR: Path = DATA_DIR / "database"

# Ruta del archivo de cookies de sesión local (carpeta sensible env/)
COOKIES_FILE: Path = BASE_DIR / "env" / "cookies.json"

# Archivo con la API key de Google Gemini (una sola línea, sin comillas)
API_KEY_FILE: Path = ENV_DIR / "api_key.txt"

def _load_google_api_key() -> str:
    """Carga la API key de Google desde env/api_key.txt (nunca se escribe en el código)."""
    try:
        if API_KEY_FILE.is_file():
            return API_KEY_FILE.read_text(encoding="utf-8").strip()
    except Exception:
        pass
    return ""

GOOGLE_API_KEY: str = _load_google_api_key()
GEMINI_MODEL: str = "gemini-3.8-flash"

# ==============================================================================
# 2. PARÁMETROS PREDETERMINADOS DE EXTRACCIÓN
# ==============================================================================
# Usuario predeterminado sugerido en la interfaz
DEFAULT_USERNAME: str = "instagram"

# Cantidad predeterminada de publicaciones a recopilar si no se especifica
DEFAULT_POSTS_LIMIT: int = 12

# Límite máximo permitido de publicaciones por extracción para evitar saturación
MAX_POSTS_LIMIT: int = 100

# URL base oficial de la plataforma
INSTAGRAM_BASE_URL: str = "https://www.instagram.com"

# ==============================================================================
# 3. CONFIGURACIÓN DEL NAVEGADOR Y SELENIUM
# ==============================================================================
# Modo headless: True para ejecutar sin ventana gráfica, False para ver el navegador
HEADLESS: bool = True

# Dimensiones de la ventana del navegador virtual
WINDOW_WIDTH: int = 1366
WINDOW_HEIGHT: int = 900

# Idioma preferido del navegador (enviado en cabeceras y preferencias)
BROWSER_LANGUAGE: str = "es-ES,es;q=0.9,en-US;q=0.8,en;q=0.7"

# Ruta opcional al binario de Chrome (None para autodetectar mediante Selenium Manager o rutas típicas de Windows)
CHROME_BINARY_PATH: str | None = None

# Tiempo máximo de carga de una página en segundos antes de timeout
PAGE_LOAD_TIMEOUT: int = 30

# Tiempo máximo de espera explícita (WebDriverWait) para que un elemento aparezca
ELEMENT_TIMEOUT: int = 12

# Tiempo de pausa tras un desplazamiento para permitir la carga asíncrona de elementos (segundos)
SCROLL_PAUSE_TIME: float = 2.0

# Número máximo de intentos de desplazamiento en la cuadrícula de publicaciones
MAX_SCROLL_ATTEMPTS: int = 15

# Número de reintentos ante fallos transitorios en etapas de red
RETRY_ATTEMPTS: int = 3

# Intervalo de espera entre reintentos en segundos
RETRY_DELAY: float = 2.5

# ==============================================================================
# 4. CAPTURAS DE PANTALLA Y DESCARGA DE IMÁGENES
# ==============================================================================
# Habilitar captura automática de pantalla del encabezado del perfil
CAPTURE_SCREENSHOT: bool = True

# Habilitar la descarga local de imágenes y miniaturas autorizadas
DOWNLOAD_IMAGES: bool = True

# Tamaño máximo permitido por imagen para descarga (15 MB)
MAX_IMAGE_SIZE_BYTES: int = 15 * 1024 * 1024

# Tiempo de espera máximo por petición de descarga de imagen (segundos)
IMAGE_DOWNLOAD_TIMEOUT: int = 15

# Resolución mínima esperada en píxeles para considerar una miniatura válida
THUMBNAIL_MIN_RESOLUTION: int = 150

# User-Agent realista para peticiones de descarga de imágenes
IMAGE_USER_AGENT: str = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)

# ==============================================================================
# 5. ALMACENAMIENTO Y EXPORTACIÓN
# ==============================================================================
# Formatos habilitados para exportación de resultados
ENABLE_JSON_STORAGE: bool = True
ENABLE_CSV_STORAGE: bool = True
ENABLE_SQLITE_STORAGE: bool = True

# Ruta a la base de datos SQLite histórica
SQLITE_DB_PATH: Path = DATABASE_DIR / "instaflow.db"

# Lista de formatos de exportación disponibles en la API
EXPORT_FORMATS: list[str] = ["json", "csv"]

# ==============================================================================
# 6. GESTIÓN DE TAREAS Y CONCURRENCIA
# ==============================================================================
# Número máximo de trabajos de scraping que pueden ejecutarse simultáneamente
MAX_CONCURRENT_JOBS: int = 2

# Límite máximo de trabajos retenidos en la memoria histórica
JOB_HISTORY_LIMIT: int = 50

# ==============================================================================
# 7. REGISTRO Y SERVIDOR WEB
# ==============================================================================
# Host y puerto para el servidor local Flask
SERVER_HOST: str = "127.0.0.1"
SERVER_PORT: int = 5000
DEBUG_MODE: bool = False

# Nivel de registro: DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_LEVEL: str = "INFO"
LOG_FORMAT: str = "[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s"


# ==============================================================================
# 8. ANÁLISIS DE AUDIENCIA (SEGUIDORES / SEGUIDOS) Y LEY DE BENFORD
# ==============================================================================
# Valores posibles del modo de audiencia. El interruptor real para alternar
# entre ambos en el código vive en scraper/audience_extractor.py
# (AudienceExtractor.MODE) -- este archivo solo fija el valor por defecto.
AUDIENCE_MODE_FOLLOWERS: str = "followers"
AUDIENCE_MODE_FOLLOWING: str = "following"
AUDIENCE_MODE: str = AUDIENCE_MODE_FOLLOWERS

# Límites de la cantidad de perfiles (seguidores o seguidos) a analizar por
# ejecución. El usuario elige la cantidad exacta desde un selector en la UI.
MIN_AUDIENCE_LIMIT: int = 200
MAX_AUDIENCE_LIMIT: int = 1000
DEFAULT_AUDIENCE_LIMIT: int = 200
AUDIENCE_LIMIT_OPTIONS: list[int] = [200, 300, 500, 750, 1000]

# Carpeta de avatares descargados de los listados de seguidores/seguidos
# (separada de media/profiles/ para no mezclarla con el perfil principal).
AUDIENCE_MEDIA_DIR: Path = MEDIA_DIR / "audience"

# Selenium se usa solo para abrir el modal y recolectar los nombres de
# usuario (requiere JavaScript real). Ese scroll puede necesitar muchos
# más intentos que la cuadrícula de publicaciones para alcanzar 200-1000.
AUDIENCE_MAX_SCROLL_ATTEMPTS: int = 500
AUDIENCE_SCROLL_PAUSE_TIME: float = 1.4

# Enriquecimiento de cada perfil (su propio followers_count): se hace con
# peticiones HTTP controladas (requests), NO abriendo cientos de páginas
# completas con Selenium -- mucho más rápido y fácil de pacear/limitar.
AUDIENCE_MAX_WORKERS: int = 4
AUDIENCE_REQUEST_DELAY: float = 0.6
AUDIENCE_REQUEST_TIMEOUT: int = 10
AUDIENCE_MAX_CONSECUTIVE_FAILURES: int = 15

# Umbrales de clasificación por chi-cuadrado (grados de libertad = 8,
# correspondientes a los 9 dígitos significativos del 1 al 9).
BENFORD_CHI2_BOT_THRESHOLD: float = 20.09          # p < 0.01
BENFORD_CHI2_POSSIBLE_BOT_THRESHOLD: float = 15.51  # p < 0.05
BENFORD_MIN_SAMPLE_SIZE: int = 10


def get_public_settings() -> dict:
    """
    Retorna un diccionario seguro con la configuración no sensible
    para exponer a la API y al panel de configuración del dashboard.
    """
    return {
        "default_username": DEFAULT_USERNAME,
        "default_posts_limit": DEFAULT_POSTS_LIMIT,
        "max_posts_limit": MAX_POSTS_LIMIT,
        "headless": HEADLESS,
        "window_size": f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}",
        "browser_language": BROWSER_LANGUAGE,
        "page_load_timeout": PAGE_LOAD_TIMEOUT,
        "element_timeout": ELEMENT_TIMEOUT,
        "max_scroll_attempts": MAX_SCROLL_ATTEMPTS,
        "capture_screenshot": CAPTURE_SCREENSHOT,
        "download_images": DOWNLOAD_IMAGES,
        "enable_json_storage": ENABLE_JSON_STORAGE,
        "enable_csv_storage": ENABLE_CSV_STORAGE,
        "enable_sqlite_storage": ENABLE_SQLITE_STORAGE,
        "max_concurrent_jobs": MAX_CONCURRENT_JOBS,
        "audience_mode": AUDIENCE_MODE,
        "min_audience_limit": MIN_AUDIENCE_LIMIT,
        "max_audience_limit": MAX_AUDIENCE_LIMIT,
        "default_audience_limit": DEFAULT_AUDIENCE_LIMIT,
        "audience_limit_options": AUDIENCE_LIMIT_OPTIONS,
        "benford_chi2_bot_threshold": BENFORD_CHI2_BOT_THRESHOLD,
        "benford_chi2_possible_bot_threshold": BENFORD_CHI2_POSSIBLE_BOT_THRESHOLD,
        "bigfive_enabled": bool(GOOGLE_API_KEY),
        "gemini_model": GEMINI_MODEL,
        "server_host": SERVER_HOST,
        "server_port": SERVER_PORT,
    }
