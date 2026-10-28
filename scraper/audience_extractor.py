"""
InstaFlow Audience Extractor (Seguidores / Seguidos)
=====================================================
Clase dedicada EXCLUSIVAMENTE a extraer el listado de audiencia (seguidores
O seguidos) de un perfil objetivo, y a enriquecer cada persona del listado
con sus propios contadores públicos (followers_count, following_count,
posts_count) para poder aplicarles la Ley de Benford.

Por qué es una clase aparte:
-----------------------------------------------------------------------
El ingeniero pidió ver en el código un único punto claro para alternar
entre analizar "seguidores" o "seguidos". Esa alternancia vive aquí, en
la constante de clase `MODE`. Nada fuera de esta clase necesita saber
si se está mirando la lista de seguidores o de seguidos: el resto del
sistema (ScraperService, la API, el frontend) solo consume el resultado.

Estrategia híbrida (dos herramientas, cada una donde rinde mejor):
-----------------------------------------------------------------------
1) Selenium (`collect_usernames`): abre el modal de Instagram y hace
   scroll para recolectar los usernames del listado. Esto SÍ requiere un
   navegador real porque el modal se construye con JavaScript.

2) requests (`enrich_user_profiles`): para leer el followers_count de
   cada uno de los 200-1000 usernames recolectados, NO se abre una página
   completa por persona con Selenium (demasiado lento y es el patrón que
   más rápido activa bloqueos). En su lugar se llama, con `requests`, al
   mismo endpoint JSON público que el propio cliente web de Instagram
   consulta para pintar un perfil. Esto permite:
     - Pacear el ritmo con precisión (un número fijo de workers +
       retraso configurable en config.py).
     - Aislar fallos por persona sin tumbar el lote completo.
     - Detectar un patrón de bloqueo (muchos fallos seguidos) y detenerse
       de forma controlada en vez de insistir a ciegas.
"""

from __future__ import annotations

import concurrent.futures
import json
import logging
import re
import time

import requests
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    ElementNotInteractableException,
    StaleElementReferenceException,
)

import config
from .exceptions import JobCancelledError
from .image_downloader import ImageDownloader
from .profile_extractor import ProfileExtractor
from .validators import is_safe_image_url

logger = logging.getLogger("instaflow.audience")

# Mismo endpoint JSON público que usa el cliente web de Instagram para
# obtener los datos de un perfil (no es una API privada/autenticada
# distinta: es la fuente de los propios og:meta que ya usa ProfileExtractor,
# solo que en formato JSON directo en vez de HTML renderizado).
IG_WEB_PROFILE_INFO_URL = "https://i.instagram.com/api/v1/users/web_profile_info/"
IG_APP_ID_HEADER = "936619743392459"

# Rutas reservadas de Instagram que nunca son un nombre de usuario real.
RESERVED_PATHS = {
    "accounts", "explore", "reels", "direct", "stories",
    "p", "reel", "about", "legal", "",
}

_USERNAME_URL_RE = re.compile(r"^https?://(?:www\.)?instagram\.com/([A-Za-z0-9_.]+)/?$")


class AudienceExtractor:
    """Extrae y enriquece el listado de seguidores o seguidos de un perfil.

    -----------------------------------------------------------------
    PUNTO ÚNICO DE ALTERNANCIA (pedido explícitamente para la clase):
    cambia esta constante para que TODO el flujo (URL del listado,
    nombre de archivo guardado, etiquetas en el dashboard) se adapte
    automáticamente entre "followers" y "following".

        MODE = config.AUDIENCE_MODE_FOLLOWERS   # <- modo actual
        MODE = config.AUDIENCE_MODE_FOLLOWING   # <- cambiar a esto en clase
    -----------------------------------------------------------------
    """

    MODE: str = config.AUDIENCE_MODE_FOLLOWING

    def __init__(
        self,
        driver: WebDriver | None = None,
        mode: str | None = None,
        session: requests.Session | None = None,
    ):
        self.driver = driver
        self.mode = mode or self.MODE
        if self.mode not in (config.AUDIENCE_MODE_FOLLOWERS, config.AUDIENCE_MODE_FOLLOWING):
            raise ValueError(f"Modo de audiencia inválido: {self.mode!r}")

        # Se activa cuando el endpoint JSON responde 401/429: a partir de ahí
        # el lote usa solo la página HTML de cada perfil (ver más abajo).
        self._profile_api_blocked = False
        self.session = session or requests.Session()
        self.session.headers.update({
            "User-Agent": config.IMAGE_USER_AGENT,
            "X-IG-App-ID": IG_APP_ID_HEADER,
            "Accept": "*/*",
        })
        self.image_downloader = ImageDownloader(session=self.session)

    @property
    def list_url_segment(self) -> str:
        """Segmento de URL de Instagram correspondiente al modo actual."""
        return "followers" if self.mode == config.AUDIENCE_MODE_FOLLOWERS else "following"

    @property
    def mode_label_es(self) -> str:
        return "seguidores" if self.mode == config.AUDIENCE_MODE_FOLLOWERS else "seguidos"

    # ==========================================================================
    # PASO 0 (Selenium): abrir el modal de seguidores/seguidos
    # ==========================================================================

    # XPaths candidatos para localizar el enlace real de "N seguidores"/
    # "N seguidos" en la cabecera del perfil, de más a menos específico.
    # Se intentan en orden porque Instagram puede cambiar su marcado y no
    # siempre expone el mismo atributo.
    def _stats_link_xpaths(self, username: str, segment: str) -> list[str]:
        return [
            f"//a[contains(@href, '/{username}/{segment}')]",
            f"//a[contains(@href, '/{segment}/')]",
            f"//*[self::a or @role='link'][contains(., '{self.mode_label_es}')]",
        ]

    def open_list_modal(self, browser, username: str, timeout: int | None = None) -> tuple[bool, str]:
        """
        Abre el modal de seguidores/seguidos del perfil ya cargado en `browser`.

        Instagram construye ese modal con JavaScript cuando una persona hace
        clic en el enlace "N seguidores"/"N seguidos" de la cabecera del
        perfil (navegación interna de React/SPA). Se prioriza reproducir
        ese clic de la forma más parecida posible a como lo hace una
        persona real:

        1) Buscar el enlace con varios XPaths candidatos (por si Instagram
           cambia el marcado) y hacer un clic NATIVO de Selenium
           (`element.click()`, el mismo mecanismo que dispara eventos de
           mouse reales) en vez de un clic simulado por JavaScript — un
           clic por JavaScript no siempre dispara el manejador de React
           que abre el modal, mientras que un clic nativo sí, porque pasa
           por la misma ruta de eventos del navegador que un clic humano.
        2) Si el clic nativo es interceptado (otro elemento tapando el
           enlace), se reintenta con un clic por JavaScript como último
           recurso antes de rendirse con ese enlace.
        3) Si ningún XPath candidato encuentra el enlace, se recurre como
           respaldo final a navegar directamente a la URL del listado.

        Retorna (modal_abierto, metodo_usado) para que el llamador pueda
        registrar en el log cuál estrategia funcionó.
        """
        segment = self.list_url_segment
        wait_timeout = timeout or config.ELEMENT_TIMEOUT

        for xpath in self._stats_link_xpaths(username, segment):
            try:
                link = browser.wait_for_element(By.XPATH, xpath, timeout=wait_timeout)
                if link is None:
                    continue

                browser.driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center'});", link
                )
                time.sleep(0.3)

                clicked = False
                try:
                    link.click()
                    clicked = True
                except (
                    ElementClickInterceptedException,
                    ElementNotInteractableException,
                    StaleElementReferenceException,
                ):
                    try:
                        browser.driver.execute_script("arguments[0].click();", link)
                        clicked = True
                    except Exception as e:
                        logger.debug(
                            "Clic de respaldo por JavaScript también falló en %s: %s",
                            self.mode_label_es, e,
                        )

                if clicked:
                    dialog = browser.wait_for_element(
                        By.XPATH, "//div[@role='dialog']", timeout=wait_timeout
                    )
                    if dialog is not None:
                        return True, f"clic real en el enlace del perfil ({xpath})"
            except Exception as e:
                logger.debug(
                    "Aviso al intentar abrir el modal de %s con %r: %s",
                    self.mode_label_es, xpath, e,
                )

        # Respaldo final: navegación directa a la URL del listado.
        list_url = f"{config.INSTAGRAM_BASE_URL}/{username}/{segment}/"
        browser.safe_get(list_url, timeout=config.PAGE_LOAD_TIMEOUT)
        dialog = browser.wait_for_element(By.XPATH, "//div[@role='dialog']", timeout=wait_timeout)
        return dialog is not None, "navegación directa a la URL"

    # ==========================================================================
    # PASO 1 (Selenium): recolectar nombres de usuario del modal
    # ==========================================================================

    def collect_usernames(
        self,
        limit: int,
        cancellation_check=None,
        log=None,
    ) -> list[str]:
        """
        Recolecta hasta `limit` nombres de usuario únicos desplazándose por
        el modal de seguidores/seguidos ya abierto en `self.driver`.

        Asume que el navegador ya está posicionado en la página del listado
        (responsabilidad del orquestador, igual que con PostExtractor).
        """
        if not self.driver:
            logger.warning("No hay driver disponible para recolectar %s.", self.mode_label_es)
            return []

        collected: dict[str, None] = {}
        scroll_attempts = 0
        consecutive_stalls = 0
        last_count = 0

        dialog = self._find_dialog_element()
        scrollable = self._find_scrollable_within(dialog) if dialog is not None else None

        while len(collected) < limit and scroll_attempts < config.AUDIENCE_MAX_SCROLL_ATTEMPTS:
            if cancellation_check and cancellation_check():
                raise JobCancelledError("Recolección de audiencia cancelada por el usuario.")

            for uname in self._extract_usernames_from_dom():
                if uname not in collected:
                    collected[uname] = None
                    if len(collected) >= limit:
                        break

            if len(collected) == last_count:
                consecutive_stalls += 1
                if consecutive_stalls >= 5:
                    if log:
                        log("warning", "No se detectaron nuevos usuarios tras varios desplazamientos; Instagram puede haber cortado el listado o requerir sesión autorizada.")
                    break
            else:
                consecutive_stalls = 0
                last_count = len(collected)

            if len(collected) >= limit:
                break

            self._scroll_once(scrollable)
            time.sleep(config.AUDIENCE_SCROLL_PAUSE_TIME)
            scroll_attempts += 1

            if log and scroll_attempts % 10 == 0:
                log("info", f"Recolectados {len(collected)}/{limit} nombres de usuario de {self.mode_label_es} hasta ahora...")

        usernames = list(collected.keys())[:limit]
        logger.info("Recolección de %s finalizada: %d usernames.", self.mode_label_es, len(usernames))
        return usernames

    def _find_dialog_element(self):
        try:
            dialogs = self.driver.find_elements(By.XPATH, "//div[@role='dialog']")
            return dialogs[-1] if dialogs else None
        except Exception:
            return None

    def _find_scrollable_within(self, dialog):
        """Encuentra, dentro del modal, el contenedor interno con scroll real."""
        if dialog is None:
            return None
        try:
            return self.driver.execute_script(
                """
                const root = arguments[0];
                const candidates = root.querySelectorAll('div');
                let best = null, bestDelta = 0;
                for (const el of candidates) {
                    const delta = el.scrollHeight - el.clientHeight;
                    if (delta > bestDelta && el.scrollHeight > 150) {
                        bestDelta = delta;
                        best = el;
                    }
                }
                return best;
                """,
                dialog,
            )
        except Exception:
            return None

    def _scroll_once(self, scrollable) -> None:
        try:
            if scrollable is not None:
                self.driver.execute_script(
                    "arguments[0].scrollTop = arguments[0].scrollHeight;", scrollable
                )
            else:
                # Sin contenedor identificado: recurrir al scroll de la ventana
                self.driver.execute_script("window.scrollBy({top: 1000, behavior: 'smooth'});")
        except Exception as e:
            logger.debug("Aviso al desplazar el listado de %s: %s", self.mode_label_es, e)

    def _extract_usernames_from_dom(self) -> set[str]:
        usernames: set[str] = set()
        try:
            anchors = self.driver.find_elements(By.XPATH, "//div[@role='dialog']//a[@href]")
            for a in anchors:
                try:
                    href = a.get_attribute("href") or ""
                except Exception:
                    continue
                match = _USERNAME_URL_RE.match(href)
                if match:
                    candidate = match.group(1).lower()
                    if candidate not in RESERVED_PATHS:
                        usernames.add(candidate)
        except Exception as e:
            logger.debug("Aviso al extraer usernames del modal: %s", e)
        return usernames

    # ==========================================================================
    # PASO 2 (requests, ritmo controlado): enriquecer cada perfil
    # ==========================================================================

    def enrich_user_profiles(
        self,
        usernames: list[str],
        cancellation_check=None,
        progress_callback=None,
        log=None,
    ) -> list[dict]:
        """
        Para cada username recolectado, consulta su propio followers_count/
        following_count/posts_count vía HTTP (sin Selenium). Aísla fallos
        por persona y corta el lote si detecta un patrón de bloqueo.
        """
        results: list[dict] = []
        if not usernames:
            return results

        if self.driver is not None:
            return self._enrich_via_browser(usernames, cancellation_check, progress_callback, log)

        consecutive_failures = 0
        done = 0
        total = len(usernames)
        stop_requested = False

        with concurrent.futures.ThreadPoolExecutor(max_workers=config.AUDIENCE_MAX_WORKERS) as pool:
            future_to_user = {}
            for uname in usernames:
                if cancellation_check and cancellation_check():
                    raise JobCancelledError("Enriquecimiento de audiencia cancelado por el usuario.")
                future_to_user[pool.submit(self._fetch_user_info, uname)] = uname
                # Pacear el envío de peticiones entre los workers disponibles.
                time.sleep(config.AUDIENCE_REQUEST_DELAY / max(1, config.AUDIENCE_MAX_WORKERS))

            for future in concurrent.futures.as_completed(future_to_user):
                uname = future_to_user[future]
                done += 1
                try:
                    info = future.result()
                except Exception as e:
                    info = None
                    logger.debug("Fallo al procesar @%s: %s", uname, e)

                if info:
                    results.append(info)
                    consecutive_failures = 0
                else:
                    consecutive_failures += 1

                if progress_callback:
                    try:
                        progress_callback(done, total)
                    except Exception:
                        pass

                if consecutive_failures >= config.AUDIENCE_MAX_CONSECUTIVE_FAILURES and not stop_requested:
                    stop_requested = True
                    if log:
                        log(
                            "warning",
                            f"Se detectaron {consecutive_failures} fallos consecutivos "
                            "(probable bloqueo/rate-limit de Instagram). Deteniendo el "
                            f"enriquecimiento con {len(results)}/{total} perfiles procesados.",
                        )
                    # Cancelar las tareas pendientes que aún no han iniciado.
                    for pending_future in future_to_user:
                        pending_future.cancel()
                    break

        return results

    def _fetch_user_info(self, username: str) -> dict | None:
        """Consulta el endpoint JSON público de perfil para un único username."""
        try:
            response = self.session.get(
                IG_WEB_PROFILE_INFO_URL,
                params={"username": username},
                timeout=config.AUDIENCE_REQUEST_TIMEOUT,
            )
            if response.status_code != 200:
                return None

            return self._parse_profile_payload(username, response.json())
        except (requests.RequestException, ValueError) as e:
            logger.debug("No se pudo consultar el perfil de @%s: %s", username, e)
            return None

    # Consulta el mismo endpoint, pero con fetch() DENTRO de Chrome: viaja
    # con las cookies de la sesión ya iniciada y la huella real del
    # navegador. Instagram responde 401/429 a esa misma petición hecha con
    # `requests`, por eso el enriquecimiento falla fuera del navegador.
    _BROWSER_FETCH_JS = """
        const done = arguments[arguments.length - 1];
        const csrf = (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || "";
        fetch("/api/v1/users/web_profile_info/?username=" + encodeURIComponent(arguments[0]), {
            credentials: "include",
            headers: {
                "X-IG-App-ID": arguments[1],
                "X-CSRFToken": csrf,
                "X-Requested-With": "XMLHttpRequest",
            },
        })
            .then(async (r) => done({ status: r.status, body: await r.text() }))
            .catch((e) => done({ status: 0, body: String(e) }));
    """

    def _enrich_via_browser(
        self,
        usernames: list[str],
        cancellation_check=None,
        progress_callback=None,
        log=None,
    ) -> list[dict]:
        """Enriquece en serie (el WebDriver no admite hilos) con ritmo pausado."""
        results: list[dict] = []
        consecutive_failures = 0
        total = len(usernames)
        self.driver.set_script_timeout(config.AUDIENCE_REQUEST_TIMEOUT + 5)

        for done, uname in enumerate(usernames, start=1):
            if cancellation_check and cancellation_check():
                raise JobCancelledError("Enriquecimiento de audiencia cancelado por el usuario.")

            info = self._fetch_user_info_via_browser(uname)
            if info:
                results.append(info)
                consecutive_failures = 0
            else:
                consecutive_failures += 1

            if progress_callback:
                try:
                    progress_callback(done, total)
                except Exception:
                    pass

            if consecutive_failures >= config.AUDIENCE_MAX_CONSECUTIVE_FAILURES:
                if log:
                    log(
                        "warning",
                        f"Se detectaron {consecutive_failures} fallos consecutivos "
                        "(probable bloqueo/rate-limit de Instagram). Deteniendo el "
                        f"enriquecimiento con {len(results)}/{total} perfiles procesados.",
                    )
                break

            time.sleep(config.AUDIENCE_REQUEST_DELAY)

        return results

    def _fetch_user_info_via_browser(self, username: str) -> dict | None:
        if not self._profile_api_blocked:
            try:
                resp = self.driver.execute_async_script(self._BROWSER_FETCH_JS, username, IG_APP_ID_HEADER)
            except Exception as e:
                logger.debug("fetch() en el navegador falló para @%s: %s", username, e)
                resp = None

            status = (resp or {}).get("status")
            if status == 200:
                try:
                    info = self._parse_profile_payload(username, json.loads(resp.get("body") or ""))
                    if info:
                        return info
                except ValueError:
                    pass
            elif status in (401, 429):
                logger.info("Endpoint JSON de perfiles limitado (HTTP %s); se usa la página HTML.", status)
                self._profile_api_blocked = True

        return self._fetch_user_info_from_profile_page(username)

    # Respaldo: la página HTML pública del perfil sigue respondiendo cuando
    # el endpoint JSON está limitado. Su og:description trae los contadores
    # ("1,2 M seguidores, 300 seguidos, 50 publicaciones"); aunque vengan
    # abreviados, el primer dígito -- lo único que usa Benford -- se conserva.
    _BROWSER_PAGE_FETCH_JS = """
        const done = arguments[arguments.length - 1];
        fetch("/" + encodeURIComponent(arguments[0]) + "/", { credentials: "include" })
            .then(async (r) => done({ status: r.status, body: await r.text() }))
            .catch((e) => done({ status: 0, body: String(e) }));
    """

    def _fetch_user_info_from_profile_page(self, username: str) -> dict | None:
        try:
            resp = self.driver.execute_async_script(self._BROWSER_PAGE_FETCH_JS, username)
        except Exception as e:
            logger.debug("No se pudo cargar la página de @%s: %s", username, e)
            return None

        status = (resp or {}).get("status")
        if status != 200:
            logger.debug("Página de @%s respondió HTTP %s", username, status)
            if status == 429:
                # Rate-limit: dar más margen antes del siguiente perfil.
                time.sleep(config.AUDIENCE_REQUEST_DELAY * 5)
            return None

        data = ProfileExtractor().extract_profile_data(username, resp.get("body") or "")
        if data.get("followers_count") is None:
            return None

        return {
            "username": username,
            "full_name": data.get("full_name"),
            "followers_count": data.get("followers_count"),
            "following_count": data.get("following_count"),
            "posts_count": data.get("posts_count"),
            "profile_image_url": data.get("profile_image_url"),
            "profile_image_path": None,
            "is_private": data.get("is_private"),
            "is_verified": data.get("is_verified"),
        }

    @staticmethod
    def _parse_profile_payload(username: str, payload) -> dict | None:
        user = ((payload or {}).get("data") or {}).get("user") or {}
        if not user:
            return None

        followers = (user.get("edge_followed_by") or {}).get("count")
        following = (user.get("edge_follow") or {}).get("count")
        posts = (user.get("edge_owner_to_timeline_media") or {}).get("count")

        return {
            "username": username,
            "full_name": user.get("full_name") or None,
            "followers_count": followers,
            "following_count": following,
            "posts_count": posts,
            "profile_image_url": user.get("profile_pic_url_hd") or user.get("profile_pic_url"),
            "profile_image_path": None,
            "is_private": user.get("is_private"),
            "is_verified": user.get("is_verified"),
        }

    # ==========================================================================
    # PASO 3: descarga local de avatares (reutiliza ImageDownloader)
    # ==========================================================================

    def download_avatars(self, users: list[dict], cancellation_check=None) -> None:
        """Descarga y valida localmente (Pillow) el avatar de cada usuario."""
        for user in users:
            if cancellation_check and cancellation_check():
                raise JobCancelledError("Descarga de avatares de audiencia cancelada por el usuario.")

            url = user.get("profile_image_url")
            if not url or not is_safe_image_url(url):
                continue

            result = self.image_downloader.download_image(
                url=url,
                target_dir=config.AUDIENCE_MEDIA_DIR,
                filename_prefix=f"aud_{self.mode}_{user.get('username', 'user')}",
            )
            if result["status"] == "downloaded":
                user["profile_image_path"] = result["local_path"]
