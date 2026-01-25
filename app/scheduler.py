import asyncio
import shutil
from datetime import datetime
from pathlib import Path
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.downloader import take_snapshot, check_camera_health
from app.logger_utils import log
from app.broadcast_manager import broadcast
from app.sunrise_utils import is_within_time_range, get_sun_times
from app.config_manager import load_config, save_config, resolve_save_dir
from app.runtime_state import set_camera_error, clear_camera_error, set_camera_health

# Global state
scheduler = None
cfg = load_config()
cfg_lock = asyncio.Lock()
is_paused = getattr(cfg, "paused", False)
STATUS_HEARTBEAT_SECONDS = 10
CAMERA_HEALTHCHECK_SECONDS = 60


# === Check whether we are inside the capture window ===
def is_active_time(cfg):
    """True if the current time is within the capture window."""
    try:
        start_time = datetime.strptime(cfg.active_start, "%H:%M").time()
        end_time = datetime.strptime(cfg.active_end, "%H:%M").time()
    except Exception:
        return True  # Fallback: always active

    active = is_within_time_range(start_time, end_time)

    # Optional: honor active weekdays if configured
    try:
        days = getattr(cfg, "active_days", []) or []
        if days:
            day_abbr = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            today = day_abbr[datetime.now().weekday()]
            if today not in days:
                return False
    except Exception:
        pass

    # If Astral is enabled, further restrict by sunrise/sunset
    if getattr(cfg, "use_astral", False):
        sunrise, sunset = get_sun_times(cfg)
        if sunrise and sunset:
            active = active and is_within_time_range(sunrise, sunset)

    return active


# === On startup: copy latest snapshot for dashboard preview ===
def copy_latest_image_on_startup(cfg):
    """Copy the newest image to static/img/last.jpg on startup."""
    app_dir = Path(__file__).resolve().parent
    data_dir = resolve_save_dir(getattr(cfg, "save_path", None))
    target_path = app_dir / "static" / "img" / "last.jpg"

    if not data_dir.exists():
        print(f"[INIT] Data directory not found: {data_dir}")
        return

    # List all images and sort by modification time
    images = sorted(
        [f for f in data_dir.iterdir() if f.is_file() and f.suffix.lower() in (".jpg", ".jpeg", ".png")],
        key=lambda f: f.stat().st_mtime,
        reverse=True
    )

    if images:
        try:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(images[0], target_path)
            print(f"[INIT] last.jpg updated -> {images[0].name}")
        except Exception as e:
            print(f"[INIT] Failed to copy last.jpg: {e}")
    else:
        print("[INIT] No existing image found to copy.")


# === Scheduler job ===
def job_snapshot():
    """Run a snapshot capture if allowed."""
    global cfg, is_paused

    if is_paused:
        log("info", "Scheduler paused - no snapshot.")
        return

    local_cfg = cfg

    if not is_active_time(local_cfg):
        log("info", "Outside active window - skipped.")
        return

    result = take_snapshot(local_cfg)
    if result:
        # After each snapshot, update last.jpg
        try:
            app_dir = Path(__file__).resolve().parent
            src = Path(result["filepath"])
            dest = app_dir / "static" / "img" / "last.jpg"
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(src, dest)
        except Exception as e:
            log("error", f"Failed to copy last.jpg: {e}")

        asyncio.run(broadcast({
            "type": "snapshot",
            "filename": result["filename"],
            "timestamp": result["timestamp"],
            "timestamp_full": result.get("timestamp_full")
        }))
        log("info", f"Snapshot saved: {result['filename']}")
        clear_camera_error()
    else:
        log("error", "Snapshot failed")
        set_camera_error("snapshot_failed", "Snapshot failed")
        try:
            asyncio.run(broadcast({
                "type": "camera_error",
                "code": "snapshot_failed",
                "message": "Snapshot failed"
            }))
        except RuntimeError as err:
            log("error", f"Failed to send camera error: {err}")


def job_status_heartbeat():
    """Send periodic status events via SSE."""
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
        log("error", f"Failed to send status heartbeat: {err}")


def job_camera_healthcheck():
    """Periodically check camera reachability without taking a snapshot."""
    local_cfg = cfg
    result = check_camera_health(local_cfg)
    checked_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if result["ok"]:
        clear_camera_error()
        set_camera_health("ok", result.get("code"), result.get("message", "OK"), checked_at)
    else:
        set_camera_health("error", result.get("code"), result.get("message", "Error"), checked_at)
    try:
        asyncio.run(broadcast({
            "type": "camera_health",
            "status": "ok" if result["ok"] else "error",
            "code": result.get("code"),
            "message": result.get("message"),
            "checked_at": checked_at,
        }))
    except RuntimeError as err:
        log("error", f"Failed to send camera health update: {err}")


# === Start scheduler ===
def start_scheduler():
    """Initialize and start the scheduler."""
    global scheduler, cfg

    if scheduler:
        scheduler.shutdown(wait=False)

    # Copy last snapshot immediately on startup
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
    scheduler.add_job(
        job_camera_healthcheck,
        trigger=IntervalTrigger(seconds=CAMERA_HEALTHCHECK_SECONDS),
        id="job_camera_healthcheck",
        replace_existing=True
    )

    scheduler.start()
    log("info", f"Scheduler started (interval: {cfg.interval_seconds}s)")


# === Stop scheduler ===
def stop_scheduler():
    """Stop the scheduler."""
    global scheduler
    if scheduler:
        scheduler.shutdown(wait=False)
        log("info", "Scheduler stopped")
        scheduler = None


# === Pause/resume control ===
async def set_paused(value: bool, *, persist: bool = True) -> None:
    """Set the scheduler paused state and optionally persist config."""
    global cfg, is_paused

    async with cfg_lock:
        is_paused = bool(value)
        if hasattr(cfg, "paused"):
            cfg.paused = is_paused
        if persist:
            try:
                save_config(cfg)
            except Exception as exc:  # pragma: no cover - logging is sufficient here
                log("warn", f"Failed to persist pause state: {exc}")

    state = "paused" if is_paused else "resumed"
    log("info", f"Scheduler {state}")
