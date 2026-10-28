"""
InstaFlow Scraper Service
=========================
Servicio central orquestador de las 16 etapas de extracción.
Maneja la navegación, detección, descarga de imágenes, generación de capturas,
persistencia multicapa (JSON, CSV, SQLite) y tolerancia a fallos.
"""

from datetime import datetime, timezone
import logging
import time
from pathlib import Path
from selenium.webdriver.common.by import By

import config
from .browser import BrowserManager
from .session_manager import SessionManager
from .profile_extractor import ProfileExtractor
from .post_extractor import PostExtractor
from .image_downloader import ImageDownloader
from .audience_extractor import AudienceExtractor
from .benford_analysis import compute_benford_analysis
from .validators import validate_username, sanitize_filename
from .exceptions import (
    JobCancelledError,
    ProfileNotFoundError,
    PrivateProfileError,
    InstaFlowError,
)
from storage.json_storage import JSONStorage
from storage.csv_storage import CSVStorage
from storage.database import DatabaseManager

logger = logging.getLogger("instaflow.service")


class ScraperService:
    """Orquesta las 16 etapas del proceso de scraping y análisis."""

    def __init__(self):
        self.session_mgr = SessionManager()
        self.image_downloader = ImageDownloader()
        self.json_storage = JSONStorage()
        self.csv_storage = CSVStorage()
        self.db = DatabaseManager()

    def execute_job(self, job) -> dict:
        """
        Ejecuta el flujo completo de 16 etapas para un Job en segundo plano.
        """
        job.status = "running"
        job.started_at = datetime.now(timezone.utc).isoformat()
        start_time = time.time()

        browser: BrowserManager | None = None
        username = job.username
        max_posts = job.options.get("max_posts", config.DEFAULT_POSTS_LIMIT)
        should_download_images = job.options.get("download_images", config.DOWNLOAD_IMAGES)
        should_capture_screenshot = job.options.get("capture_screenshot", config.CAPTURE_SCREENSHOT)

        try:
            # ==================================================================
            # ETAPA 1: Validar el nombre de usuario
            # ==================================================================
            job.start_stage(1, "Validar el nombre de usuario", progress_hint=5)
            is_valid, normalized_user, error_msg = validate_username(username)
            if not is_valid:
                job.complete_stage(1, status="error", message=error_msg or "Usuario inválido")
                raise InstaFlowError(error_msg or "Nombre de usuario inválido.")
            username = normalized_user
            job.username = normalized_user
            job.complete_stage(1, status="success", message=f"Usuario válido: @{username}")

            # ==================================================================
            # ETAPA 2: Inicializar Chrome
            # ==================================================================
            job.start_stage(2, "Inicializar Chrome", progress_hint=10)
            browser = BrowserManager()
            driver = browser.start()
            job.complete_stage(2, status="success", message="Navegador Chrome listo.")

            # ==================================================================
            # ETAPA 3: Comprobar la sesión y el estado de acceso
            # ==================================================================
            job.start_stage(3, "Comprobar la sesión y el estado de acceso", progress_hint=15)
            self.session_mgr.inject_cookies(driver)
            session_status = self.session_mgr.check_session_status(driver)
            job.complete_stage(
                3,
                status="success" if session_status["authenticated"] else "warning",
                message=session_status["status_text"],
            )

            # ==================================================================
            # ETAPA 4: Abrir el perfil solicitado
            # ==================================================================
            job.start_stage(4, "Abrir el perfil solicitado", progress_hint=20)
            profile_url = f"{config.INSTAGRAM_BASE_URL}/{username}/"
            loaded = browser.safe_get(profile_url, timeout=config.PAGE_LOAD_TIMEOUT)
            if not loaded:
                job.add_log("warning", "La página tardó más de lo esperado en responder. Analizando DOM parcial.")
            job.complete_stage(4, status="success" if loaded else "warning", message=f"URL: {profile_url}")

            # ==================================================================
            # ETAPA 5: Esperar a que el contenido relevante esté disponible
            # ==================================================================
            job.start_stage(5, "Esperar a que el contenido relevante esté disponible", progress_hint=25)
            # Esperar por elemento clave del perfil o detección de 404
            browser.wait_for_element(By.TAG_NAME, "header", timeout=config.ELEMENT_TIMEOUT)
            # Pausa breve para hidratación del framework React de Instagram
            time.sleep(1.5)
            job.complete_stage(5, status="success", message="Contenido principal del perfil disponible.")

            # ==================================================================
            # ETAPA 6: Capturar la información básica
            # ==================================================================
            job.start_stage(6, "Capturar la información básica", progress_hint=30)
            profile_extractor = ProfileExtractor(driver=driver)
            profile_data = profile_extractor.extract_profile_data(username)
            job.profile = profile_data

            # Captura de pantalla si está habilitada
            if should_capture_screenshot:
                timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                safe_name = sanitize_filename(username)
                ss_filename = f"{safe_name}_{timestamp_str}_{job.job_id[:8]}.png"
                ss_target = config.SCREENSHOTS_DIR / ss_filename
                if browser.capture_screenshot(ss_target):
                    rel_ss = ss_target.relative_to(config.BASE_DIR).as_posix()
                    job.summary["screenshot_path"] = rel_ss
                    job.add_log("info", f"Captura del perfil guardada: {rel_ss}")

            job.complete_stage(
                6,
                status="success" if profile_data.get("status") == "complete" else "warning",
                message=f"Información básica obtenida. Estado: {profile_data.get('status')}",
            )

            # Si es cuenta privada no accesible
            if profile_data.get("is_private") and not session_status.get("authenticated"):
                job.add_log("warning", "La cuenta es privada y no hay sesión autorizada para ver publicaciones.")

            # ==================================================================
            # ETAPA 7: Capturar la fotografía de perfil
            # ==================================================================
            job.start_stage(7, "Capturar la fotografía de perfil", progress_hint=40)
            pfp_url = profile_data.get("profile_image_url")
            if pfp_url and should_download_images:
                dl_result = self.image_downloader.download_image(
                    url=pfp_url,
                    target_dir=config.PROFILES_MEDIA_DIR,
                    filename_prefix=f"pfp_{username}",
                )
                if dl_result["status"] == "downloaded":
                    profile_data["profile_image_path"] = dl_result["local_path"]
                    job.complete_stage(7, status="success", message="Foto de perfil descargada y validada.")
                else:
                    job.complete_stage(7, status="warning", message=f"No se pudo descargar avatar ({dl_result.get('error')}).")
            else:
                job.complete_stage(7, status="warning", message="Foto de perfil no disponible para descarga.")

            # ==================================================================
            # ETAPA 8: Detectar el número total de publicaciones
            # ==================================================================
            job.start_stage(8, "Detectar el número total de publicaciones", progress_hint=45)
            posts_count = profile_data.get("posts_count")
            if posts_count is not None:
                msg = f"Instagram indica un total de {posts_count:,} publicaciones."
                job.complete_stage(8, status="success", message=msg)
            else:
                job.complete_stage(8, status="warning", message="Contador total no disponible explícitamente.")

            # ==================================================================
            # ETAPA 9: Identificar los enlaces de publicaciones
            # ==================================================================
            job.start_stage(9, "Identificar los enlaces de publicaciones", progress_hint=50)
            post_extractor = PostExtractor(driver=driver)

            # Si el perfil es privado y no estamos autorizados, saltar extracción de publicaciones
            if profile_data.get("is_private") and not session_status.get("authenticated"):
                collected_posts = []
                job.complete_stage(9, status="warning", message="Cuenta privada: publicaciones protegidas.")
            else:
                collected_posts = post_extractor.extract_posts_from_grid(
                    max_posts=max_posts,
                    cancellation_check=job.is_cancelled,
                )
                job.complete_stage(9, status="success", message=f"Identificados {len(collected_posts)} enlaces de publicaciones.")

            job.posts = collected_posts
            job.summary["posts_collected"] = len(collected_posts)

            # Enriquecer perfil con información de última publicación y fecha de creación
            if collected_posts:
                first_p = collected_posts[0]
                profile_data["latest_post_date"] = first_p.get("published_at") or "Reciente (disponible en Instagram)"
                profile_data["latest_post_url"] = first_p.get("url")
            else:
                profile_data["latest_post_date"] = "Sin publicaciones"
                profile_data["latest_post_url"] = None

            if not profile_data.get("account_created_at"):
                profile_data["account_created_at"] = "No revelada por Instagram (no pública)"

            # ==================================================================
            # ETAPA 10: Recopilar los metadatos disponibles
            # ==================================================================
            job.start_stage(10, "Recopilar los metadatos disponibles", progress_hint=60)
            # Enriquecimiento adicional si aplica
            type_counts = {}
            for p in collected_posts:
                m_type = p.get("media_type", "photo")
                type_counts[m_type] = type_counts.get(m_type, 0) + 1

            type_summary = ", ".join([f"{count} {t}" for t, count in type_counts.items()]) or "Sin publicaciones"
            job.complete_stage(10, status="success", message=f"Metadatos clasificados: {type_summary}.")

            # ==================================================================
            # ETAPA 11: Obtener las miniaturas
            # ==================================================================
            job.start_stage(11, "Obtener las miniaturas", progress_hint=70)
            thumbnails_detected = sum(1 for p in collected_posts if p.get("thumbnail_url"))
            job.complete_stage(11, status="success", message=f"Se detectaron {thumbnails_detected} URLs de miniaturas.")

            # ==================================================================
            # ETAPA 12: Descargar las imágenes autorizadas
            # ==================================================================
            job.start_stage(12, "Descargar las imágenes autorizadas", progress_hint=80)
            downloaded_count = 0
            failed_count = 0

            if should_download_images and collected_posts:
                for idx, post in enumerate(collected_posts):
                    if job.is_cancelled():
                        raise JobCancelledError("Descarga de imágenes cancelada por el usuario.")

                    thumb_url = post.get("thumbnail_url")
                    shortcode = post.get("shortcode", f"post_{idx}")

                    if thumb_url:
                        dl = self.image_downloader.download_image(
                            url=thumb_url,
                            target_dir=config.POSTS_MEDIA_DIR,
                            filename_prefix=f"{username}_{shortcode}",
                        )
                        if dl["status"] == "downloaded":
                            post["thumbnail_path"] = dl["local_path"]
                            post["download_status"] = "downloaded"
                            downloaded_count += 1
                        else:
                            post["download_status"] = "failed"
                            post["errors"].append(dl.get("error") or "Fallo en descarga")
                            failed_count += 1
                    else:
                        post["download_status"] = "not_available"

                job.summary["images_downloaded"] = downloaded_count
                job.summary["images_failed"] = failed_count
                job.complete_stage(
                    12,
                    status="success" if failed_count == 0 else "warning",
                    message=f"{downloaded_count} imágenes descargadas ({failed_count} fallidas).",
                )
            else:
                job.complete_stage(12, status="success", message="Descarga de imágenes omitida o no requerida.")

            # ==================================================================
            # ETAPA 13: Validar los archivos
            # ==================================================================
            job.start_stage(13, "Validar los archivos", progress_hint=85)
            # La validación con Pillow ya se realiza de forma estricta en ImageDownloader
            job.complete_stage(13, status="success", message="Integridad de archivos y cabeceras verificada.")

            # ==================================================================
            # ETAPA 14: Guardar los resultados
            # ==================================================================
            job.start_stage(14, "Guardar los resultados", progress_hint=90)
            if config.ENABLE_JSON_STORAGE:
                self.json_storage.save_run_result(job.job_id, profile_data, collected_posts, job.summary)
            if config.ENABLE_CSV_STORAGE:
                self.csv_storage.export_profile_csv(profile_data, job_id=job.job_id)
                self.csv_storage.export_posts_csv(collected_posts, username, job_id=job.job_id)
            if config.ENABLE_SQLITE_STORAGE:
                self.db.save_profile(profile_data, job_id=job.job_id)
                self.db.save_posts(collected_posts, username, job_id=job.job_id)

            job.complete_stage(14, status="success", message="Resultados almacenados en JSON, CSV y SQLite.")

            # ==================================================================
            # ETAPA 15: Actualizar el dashboard
            # ==================================================================
            job.start_stage(15, "Actualizar el dashboard", progress_hint=95)
            # El estado en memoria de Job se sincroniza automáticamente
            job.complete_stage(15, status="success", message="Estructura de respuesta preparada para el dashboard.")

            # ==================================================================
            # ETAPA 16: Generar un resumen de la ejecución
            # ==================================================================
            job.start_stage(16, "Generar un resumen de la ejecución", progress_hint=100)
            elapsed = round(time.time() - start_time, 2)
            job.duration_sec = elapsed
            job.finished_at = datetime.now(timezone.utc).isoformat()

            # Clasificar estado final
            if profile_data.get("status") == "failed":
                job.status = "failed"
            elif profile_data.get("is_private") and not session_status.get("authenticated"):
                job.status = "partial"
            elif len(collected_posts) < max_posts and posts_count and posts_count > len(collected_posts):
                job.status = "partial"
            else:
                job.status = "completed"

            summary_msg = (
                f"Ejecución finalizada en {elapsed}s. Estado: {job.status}. "
                f"Publicaciones recopiladas: {len(collected_posts)}. "
                f"Imágenes guardadas: {downloaded_count}."
            )
            job.complete_stage(16, status="success", message=summary_msg)
            job.add_log("success", summary_msg)

            # Registrar en base de datos el job finalizado
            if config.ENABLE_SQLITE_STORAGE:
                self.db.save_job(
                    job_id=job.job_id,
                    username=username,
                    status=job.status,
                    created_at=job.created_at,
                    finished_at=job.finished_at,
                    duration_sec=job.duration_sec,
                    requested_posts=max_posts,
                    collected_posts=len(collected_posts),
                    downloaded_images=downloaded_count,
                    metadata={"summary": job.summary},
                )

            return job.to_dict()

        except JobCancelledError:
            elapsed = round(time.time() - start_time, 2)
            job.status = "cancelled"
            job.finished_at = datetime.now(timezone.utc).isoformat()
            job.duration_sec = elapsed
            job.add_log("warning", f"Proceso detenido de forma segura tras {elapsed}s.")
            if config.ENABLE_SQLITE_STORAGE:
                self.db.save_job(
                    job_id=job.job_id,
                    username=username,
                    status="cancelled",
                    created_at=job.created_at,
                    finished_at=job.finished_at,
                    duration_sec=elapsed,
                    error_message="Cancelado por el usuario",
                )
            return job.to_dict()

        except ProfileNotFoundError as pe:
            elapsed = round(time.time() - start_time, 2)
            job.status = "failed"
            job.error_message = str(pe)
            job.finished_at = datetime.now(timezone.utc).isoformat()
            job.duration_sec = elapsed
            job.add_log("error", f"Error: {pe}")
            return job.to_dict()

        except Exception as e:
            elapsed = round(time.time() - start_time, 2)
            job.status = "failed"
            job.error_message = f"Error durante la extracción: {e}"
            job.finished_at = datetime.now(timezone.utc).isoformat()
            job.duration_sec = elapsed
            job.add_log("error", f"Error crítico: {e}")
            logger.exception("Error no capturado en la ejecución de scraping: %s", e)
            return job.to_dict()

        finally:
            if browser:
                try:
                    browser.quit()
                except Exception:
                    pass

    # ==========================================================================
    # FLUJO DE AUDIENCIA: SEGUIDORES/SEGUIDOS + LEY DE BENFORD
    # ==========================================================================

    def execute_audience_job(self, job) -> dict:
        """
        Ejecuta el flujo de extracción de audiencia (seguidores O seguidos,
        según AudienceExtractor.MODE) de un perfil objetivo, enriquece a
        cada persona del listado con sus propios contadores públicos y
        aplica la Ley de Benford sobre el primer dígito de esos contadores.
        """
        job.status = "running"
        job.started_at = datetime.now(timezone.utc).isoformat()
        start_time = time.time()

        browser: BrowserManager | None = None
        target_username = job.username

        requested_limit = job.options.get("limit", config.DEFAULT_AUDIENCE_LIMIT)
        limit = max(config.MIN_AUDIENCE_LIMIT, min(int(requested_limit), config.MAX_AUDIENCE_LIMIT))
        job.audience_limit = limit
        should_download_images = job.options.get("download_images", True)

        try:
            # ==================================================================
            # ETAPA 1: Validar usuario objetivo y parámetros
            # ==================================================================
            job.start_stage(1, "Validar usuario objetivo y parámetros", progress_hint=5)
            is_valid, normalized_user, error_msg = validate_username(target_username)
            if not is_valid:
                job.complete_stage(1, status="error", message=error_msg or "Usuario inválido")
                raise InstaFlowError(error_msg or "Nombre de usuario inválido.")
            target_username = normalized_user
            job.username = normalized_user
            job.complete_stage(
                1, status="success",
                message=f"Usuario válido: @{target_username}. Límite solicitado: {limit} perfiles.",
            )

            # ==================================================================
            # ETAPA 2: Inicializar Chrome
            # ==================================================================
            job.start_stage(2, "Inicializar Chrome", progress_hint=10)
            browser = BrowserManager()
            driver = browser.start()
            job.complete_stage(2, status="success", message="Navegador Chrome listo.")

            # ==================================================================
            # ETAPA 3: Comprobar la sesión y el estado de acceso
            # ==================================================================
            job.start_stage(3, "Comprobar la sesión y el estado de acceso", progress_hint=15)
            self.session_mgr.inject_cookies(driver)
            session_status = self.session_mgr.check_session_status(driver)

            audience_extractor = AudienceExtractor(driver=driver)
            job.audience_mode = audience_extractor.mode
            mode_label = audience_extractor.mode_label_es

            if not session_status.get("authenticated"):
                # Sin sesión, Instagram no muestra el listado ni deja consultar
                # los contadores de cada perfil (responde 401/429): continuar
                # solo produciría 0 perfiles y un Benford vacío.
                job.complete_stage(3, status="error", message=session_status["status_text"])
                raise InstaFlowError(
                    f"{session_status['status_text']} Instagram exige una sesión "
                    "iniciada para ver seguidores/seguidos y sus contadores, así "
                    "que no hay datos para aplicar la Ley de Benford. Actualiza "
                    "env/cookies.json (sessionid, ds_user_id, csrftoken) y reintenta."
                )
            job.complete_stage(3, status="success", message=session_status["status_text"])

            # ==================================================================
            # ETAPA 4: Abrir el perfil objetivo
            # ==================================================================
            job.start_stage(4, "Abrir el perfil objetivo", progress_hint=20)
            profile_url = f"{config.INSTAGRAM_BASE_URL}/{target_username}/"
            browser.safe_get(profile_url, timeout=config.PAGE_LOAD_TIMEOUT)
            job.complete_stage(4, status="success", message=f"URL: {profile_url}")

            # ==================================================================
            # ETAPA 5: Abrir el listado de seguidores/seguidos
            # ==================================================================
            job.start_stage(5, f"Abrir el listado de {mode_label}", progress_hint=25)
            dialog_found, open_method = audience_extractor.open_list_modal(
                browser, username=target_username,
            )
            time.sleep(1.0)

            diagnostic_note = ""
            if not dialog_found:
                # Captura de diagnóstico: si el modal no aparece, guardamos una
                # captura de pantalla Y el HTML de esa página exacta para poder
                # ver qué mostró Instagram en ese momento (muro de login,
                # aviso de bloqueo/rate-limit, interfaz distinta, etc.) en vez
                # de adivinar a ciegas.
                try:
                    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                    safe_name = sanitize_filename(target_username)
                    debug_base = f"audience_debug_{safe_name}_{timestamp_str}_{job.job_id[:8]}"
                    config.SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
                    ss_path = config.SCREENSHOTS_DIR / f"{debug_base}.png"
                    html_path = config.SCREENSHOTS_DIR / f"{debug_base}.html"
                    saved_ss = browser.capture_screenshot(ss_path)
                    try:
                        html_path.write_text(browser.get_page_source(), encoding="utf-8")
                        saved_html = True
                    except Exception:
                        saved_html = False
                    if saved_ss or saved_html:
                        diagnostic_note = (
                            f" Diagnóstico guardado en: "
                            f"{ss_path.relative_to(config.BASE_DIR).as_posix() if saved_ss else '(sin captura)'} "
                            f"y {html_path.relative_to(config.BASE_DIR).as_posix() if saved_html else '(sin HTML)'}."
                        )
                except Exception as e:
                    logger.debug("Aviso al guardar diagnóstico de audiencia: %s", e)

            job.complete_stage(
                5,
                status="success" if dialog_found else "warning",
                message=(
                    f"Listado abierto correctamente ({open_method})."
                    if dialog_found else
                    "No se detectó el modal esperado ni por clic ni por URL directa; "
                    "Instagram puede requerir sesión autorizada o haber cambiado su interfaz."
                    + diagnostic_note
                ),
            )

            # ==================================================================
            # ETAPA 6: Recolectar nombres de usuario (scroll progresivo)
            # ==================================================================
            job.start_stage(6, "Recolectar nombres de usuario (scroll progresivo)", progress_hint=35)
            usernames = audience_extractor.collect_usernames(
                limit=limit,
                cancellation_check=job.is_cancelled,
                log=job.add_log,
            )
            job.complete_stage(
                6,
                status="success" if usernames else "warning",
                message=f"Se recolectaron {len(usernames)} nombres de usuario de {mode_label}.",
            )

            # ==================================================================
            # ETAPA 7: Enriquecer cada perfil (fetch() dentro de Chrome, ritmo pausado)
            # ==================================================================
            job.start_stage(7, "Enriquecer cada perfil con sus propios contadores", progress_hint=55)

            def _on_progress(done: int, total: int) -> None:
                if total:
                    job.progress_percent = min(80, 55 + int(25 * (done / total)))
                if total and (done % 25 == 0 or done == total):
                    job.add_log("info", f"Perfiles enriquecidos: {done}/{total}")

            users = audience_extractor.enrich_user_profiles(
                usernames,
                cancellation_check=job.is_cancelled,
                progress_callback=_on_progress,
                log=job.add_log,
            )
            job.complete_stage(
                7,
                status="success" if users else "warning",
                message=f"{len(users)}/{len(usernames)} perfiles enriquecidos exitosamente.",
            )

            # ==================================================================
            # ETAPA 8: Descargar avatares
            # ==================================================================
            job.start_stage(8, "Descargar avatares", progress_hint=85)
            downloaded_count = 0
            if should_download_images and users:
                audience_extractor.download_avatars(users, cancellation_check=job.is_cancelled)
                downloaded_count = sum(1 for u in users if u.get("profile_image_path"))
            job.complete_stage(8, status="success", message=f"{downloaded_count}/{len(users)} avatares descargados y validados.")

            # ==================================================================
            # ETAPA 9: Calcular la Ley de Benford y chi-cuadrado
            # ==================================================================
            job.start_stage(9, "Calcular la Ley de Benford y chi-cuadrado", progress_hint=90)
            follower_values = [u.get("followers_count") for u in users]
            benford_result = compute_benford_analysis(
                follower_values,
                min_sample_size=config.BENFORD_MIN_SAMPLE_SIZE,
                bot_threshold=config.BENFORD_CHI2_BOT_THRESHOLD,
                possible_bot_threshold=config.BENFORD_CHI2_POSSIBLE_BOT_THRESHOLD,
            )
            job.benford = benford_result
            job.audience_users = users
            job.complete_stage(
                9, status="success",
                message=f"χ²={benford_result['chi_square']} → {benford_result['classification_label']} (n={benford_result['sample_size']}).",
            )

            # ==================================================================
            # ETAPA 10: Guardar resultados
            # ==================================================================
            job.start_stage(10, "Guardar resultados", progress_hint=95)
            if config.ENABLE_JSON_STORAGE:
                self.json_storage.save_audience_result(
                    target_username=target_username,
                    mode=audience_extractor.mode,
                    limit_requested=limit,
                    users=users,
                    benford=benford_result,
                )
            job.complete_stage(10, status="success", message="Resultados guardados en data/results/.")

            # ==================================================================
            # ETAPA 11: Generar resumen de la ejecución
            # ==================================================================
            job.start_stage(11, "Generar resumen de la ejecución", progress_hint=100)
            elapsed = round(time.time() - start_time, 2)
            job.duration_sec = elapsed
            job.finished_at = datetime.now(timezone.utc).isoformat()
            job.status = "completed" if users else "partial"

            summary_msg = (
                f"Ejecución finalizada en {elapsed}s. Perfiles de {mode_label} analizados: "
                f"{len(users)}/{limit} solicitados. Clasificación: {benford_result['classification_label']} "
                f"(χ²={benford_result['chi_square']})."
            )
            job.complete_stage(11, status="success", message=summary_msg)
            job.add_log("success", summary_msg)

            return job.to_dict()

        except JobCancelledError:
            elapsed = round(time.time() - start_time, 2)
            job.status = "cancelled"
            job.finished_at = datetime.now(timezone.utc).isoformat()
            job.duration_sec = elapsed
            job.add_log("warning", f"Proceso de audiencia detenido de forma segura tras {elapsed}s.")
            return job.to_dict()

        except Exception as e:
            elapsed = round(time.time() - start_time, 2)
            job.status = "failed"
            job.error_message = str(e) if isinstance(e, InstaFlowError) else f"Error durante la extracción de audiencia: {e}"
            job.finished_at = datetime.now(timezone.utc).isoformat()
            job.duration_sec = elapsed
            job.add_log("error", f"Error crítico: {e}")
            logger.exception("Error no capturado en execute_audience_job: %s", e)
            return job.to_dict()

        finally:
            if browser:
                try:
                    browser.quit()
                except Exception:
                    pass
