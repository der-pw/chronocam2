import asyncio
import shutil
from datetime import datetime
from pathlib import Path
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.downloader import take_snapshot
from app.logger_utils import log
from app.broadcast_manager import broadcast
from app.sunrise_utils import is_within_time_range, get_sun_times
from app.config_manager import load_config
from app.runtime_state import set_camera_error, clear_camera_error

# Globale Variablen
scheduler = None
cfg = load_config()
cfg_lock = asyncio.Lock()
is_paused = False
STATUS_HEARTBEAT_SECONDS = 10


# === Prüfen, ob aktuell Aufnahmezeit ist ===
def is_active_time(cfg):
    """True, wenn sich die aktuelle Zeit innerhalb des Aufnahmefensters befindet."""
    try:
        start_time = datetime.strptime(cfg.active_start, "%H:%M").time()
        end_time = datetime.strptime(cfg.active_end, "%H:%M").time()
    except Exception:
        return True  # Fallback: immer aktiv

    active = is_within_time_range(start_time, end_time)

    # Optional: Wochentage berücksichtigen, falls gesetzt
    try:
        days = getattr(cfg, "active_days", []) or []
        if days:
            day_abbr = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            today = day_abbr[datetime.now().weekday()]
            if today not in days:
                return False
    except Exception:
        pass

    # Falls Astral aktiviert ist → Sonnenzeiten berücksichtigen
    if getattr(cfg, "use_astral", False):
        sunrise, sunset = get_sun_times(cfg)
        if sunrise and sunset:
            active = active and is_within_time_range(sunrise, sunset)

    return active


# === 🆕 Neu: Letztes vorhandenes Bild beim Start kopieren ===
def copy_latest_image_on_startup(cfg):
    """Kopiert das neueste vorhandene Bild aus data/ nach static/img/last.jpg."""
    app_dir = Path(__file__).resolve().parent
    data_dir = (app_dir / cfg.save_path).resolve()
    target_path = app_dir / "static" / "img" / "last.jpg"

    if not data_dir.exists():
        print(f"[INIT] Kein Datenverzeichnis gefunden: {data_dir}")
        return

    # Alle Bilddateien auflisten, nach Änderungszeit sortieren
    images = sorted(
        [f for f in data_dir.iterdir() if f.is_file() and f.suffix.lower() in (".jpg", ".jpeg", ".png")],
        key=lambda f: f.stat().st_mtime,
        reverse=True
    )

    if images:
        try:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(images[0], target_path)
            print(f"[INIT] last.jpg aktualisiert → {images[0].name}")
        except Exception as e:
            print(f"[INIT] Konnte last.jpg nicht kopieren: {e}")
    else:
        print("[INIT] Kein vorhandenes Bild zum Kopieren gefunden.")


# === Scheduler-Job ===
def job_snapshot():
    """Führt Snapshot-Aufnahme aus, falls erlaubt."""
    global cfg, is_paused

    if is_paused:
        log("info", "Scheduler pausiert – kein Snapshot.")
        return

    local_cfg = cfg

    if not is_active_time(local_cfg):
        log("info", "Nicht im aktiven Zeitraum – übersprungen.")
        return

    result = take_snapshot(local_cfg)
    if result:
        # Nach jedem neuen Snapshot → last.jpg aktualisieren
        try:
            app_dir = Path(__file__).resolve().parent
            src = Path(result["filepath"])
            dest = app_dir / "static" / "img" / "last.jpg"
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(src, dest)
        except Exception as e:
            log("error", f"Fehler beim Kopieren von last.jpg: {e}")

        asyncio.run(broadcast({
            "type": "snapshot",
            "filename": result["filename"],
            "timestamp": result["timestamp"]
        }))
        log("info", f"Snapshot gespeichert: {result['filename']}")
        clear_camera_error()
    else:
        log("error", "Snapshot fehlgeschlagen")
        set_camera_error("snapshot_failed", "Snapshot fehlgeschlagen")
        try:
            asyncio.run(broadcast({
                "type": "camera_error",
                "code": "snapshot_failed",
                "message": "Snapshot fehlgeschlagen"
            }))
        except RuntimeError as err:
            log("error", f"Kamera-Fehler konnte nicht gesendet werden: {err}")


def job_status_heartbeat():
    """Sendet regelmäßige Status-Events via SSE."""
    global cfg, is_paused

    if is_paused:
        status = "paused"
    else:
        status = "running" if is_active_time(cfg) else "waiting_window"

    try:
        asyncio.run(broadcast({
            "type": "status",
            "status": status
        }))
    except RuntimeError as err:
        log("error", f"Status-Heartbeat konnte nicht gesendet werden: {err}")


# === Scheduler starten ===
def start_scheduler():
    """Initialisiert und startet den Scheduler."""
    global scheduler, cfg

    if scheduler:
        scheduler.shutdown(wait=False)

    # 🆕 Letztes vorhandenes Bild direkt beim Start kopieren
    copy_latest_image_on_startup(cfg)

    scheduler = BackgroundScheduler(timezone="Europe/Berlin")

    scheduler.add_job(
        job_snapshot,
        trigger=IntervalTrigger(seconds=cfg.interval_seconds),
        id="job_snapshot",
        replace_existing=True
    )
    scheduler.add_job(
        job_status_heartbeat,
        trigger=IntervalTrigger(seconds=STATUS_HEARTBEAT_SECONDS),
        id="job_status_heartbeat",
        replace_existing=True
    )

    scheduler.start()
    log("info", f"Scheduler gestartet (Intervall: {cfg.interval_seconds}s)")


# === Scheduler stoppen ===
def stop_scheduler():
    """Beendet den Scheduler."""
    global scheduler
    if scheduler:
        scheduler.shutdown(wait=False)
        log("info", "Scheduler gestoppt")
        scheduler = None


# === Pause/Resume steuern ===
def set_paused(value: bool) -> None:
    """Setzt den pausiert-Status des Schedulers."""
    global is_paused
    is_paused = bool(value)
    state = "pausiert" if is_paused else "fortgesetzt"
    log("info", f"Scheduler {state}")
