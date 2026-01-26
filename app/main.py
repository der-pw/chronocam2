from fastapi import FastAPI, Request, Form
from typing import List
from fastapi.responses import HTMLResponse, StreamingResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
import asyncio
import json
from datetime import datetime

from app.config_manager import load_config, save_config, resolve_save_dir
from app.models import ConfigModel
from app.scheduler import start_scheduler, stop_scheduler, cfg_lock, cfg, set_paused, is_active_time
from app import i18n
from app.broadcast_manager import clients, broadcast
from app.logger_utils import log
from app.downloader import take_snapshot, check_camera_health
from app.sunrise_utils import get_sun_times
from app.runtime_state import (
    set_camera_error,
    clear_camera_error,
    get_camera_error,
    set_camera_health,
    get_camera_health,
    set_image_stats,
    get_image_stats,
)

# === FastAPI App ===
app = FastAPI()

# === Static Mount (CSS, JS, images) ===
app.mount(
    "/static",
    StaticFiles(directory=Path(__file__).parent / "static"),
    name="static"
)

# === Templates ===
APP_VERSION = "2.2.4"
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
templates.env.globals["app_version"] = APP_VERSION


def _compute_image_stats(save_path: Path) -> tuple[int, str | None, str | None]:
    """Compute image count and last snapshot timestamps from disk."""
    stats = get_image_stats()
    if stats:
        count = stats.get("count", 0)
        last_snapshot_ts = stats.get("last_snapshot")
        last_snapshot_full = stats.get("last_snapshot_full")
    else:
        count, last_snapshot_ts, last_snapshot_full = _compute_image_stats(save_path)
        set_image_stats(count, last_snapshot_ts, last_snapshot_full)
    return count, last_snapshot_ts, last_snapshot_full

# === SSE: server-sent events for live updates ===
@app.get("/events")
async def sse_events():
    """SSE endpoint for dashboard updates (snapshots, status, etc.)."""
    queue = asyncio.Queue()
    clients.add(queue)

    async def event_generator():
        try:
            while True:
                msg = await queue.get()
                yield f"data: {json.dumps(msg)}\n\n"
        except asyncio.CancelledError:
            clients.remove(queue)
            raise

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# === Index page ===
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    async with cfg_lock:
        local_cfg = cfg

    # Cache buster for last.jpg to ensure immediate refresh
    cache_buster = int(datetime.now().timestamp())

    tr = i18n.load_translations(getattr(local_cfg, "language", "de"))
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "cfg": local_cfg,
            "cache_buster": cache_buster,
            "tr": tr,
            "lang": getattr(local_cfg, "language", "de"),
        }
    )


# === Settings page ===
@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    """Render the settings page (original layout)."""
    async with cfg_lock:
        local_cfg = cfg
    message = None
    if request.query_params.get("saved"):
        message = "Einstellungen gespeichert!"
    langs = i18n.available_languages()
    tr = i18n.load_translations(getattr(local_cfg, "language", "de"))
    return templates.TemplateResponse(
        "settings.html",
        {
            "request": request,
            "cfg": local_cfg,
            "message": message,
            "langs": langs,
            "tr": tr,
            "lang": getattr(local_cfg, "language", "de"),
        }
    )


# === Save settings ===
@app.post("/update", response_class=HTMLResponse)
async def update_settings(
    request: Request,
    CAM_URL: str = Form(...),
    INSTANCE_NAME: str = Form(""),
    INTERVAL_SECONDS: int = Form(...),
    SAVE_PATH: str = Form(...),
    AUTH_TYPE: str = Form("none"),
    USERNAME: str = Form(""),
    PASSWORD: str = Form(""),
    ACTIVE_START: str = Form("06:00"),
    ACTIVE_END: str = Form("22:00"),
    ACTIVE_DAYS: List[str] = Form([]),
    USE_ASTRAL: str = Form(None),
    CITY_LAT: float = Form(48.137),
    CITY_LON: float = Form(11.575),
    CITY_TZ: str = Form("Europe/Berlin"),
    LANGUAGE: str = Form("de"),
):
    """Persist settings and redirect back to /settings with a success flag."""
    async with cfg_lock:
        cfg.cam_url = CAM_URL
        cfg.instance_name = INSTANCE_NAME.strip() or None
        cfg.interval_seconds = INTERVAL_SECONDS
        cfg.save_path = SAVE_PATH
        cfg.auth_type = AUTH_TYPE
        cfg.username = USERNAME
        if PASSWORD.strip():
            cfg.password = PASSWORD
        cfg.active_start = ACTIVE_START
        cfg.active_end = ACTIVE_END
        cfg.active_days = [d for d in ACTIVE_DAYS if d]
        cfg.use_astral = USE_ASTRAL is not None
        cfg.city_lat = CITY_LAT
        cfg.city_lon = CITY_LON
        cfg.city_tz = CITY_TZ
        cfg.language = LANGUAGE or getattr(cfg, "language", "de")
        save_config(cfg)

    stop_scheduler()
    start_scheduler()
    # Run a quick healthcheck after saving to provide immediate feedback
    health = await asyncio.to_thread(check_camera_health, cfg)
    checked_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if health.get("ok"):
        clear_camera_error()
        set_camera_health("ok", health.get("code"), health.get("message", "OK"), checked_at)
    else:
        set_camera_health("error", health.get("code"), health.get("message", "Error"), checked_at)
    await broadcast({
        "type": "camera_health",
        "status": "ok" if health.get("ok") else "error",
        "code": health.get("code"),
        "message": health.get("message"),
        "checked_at": checked_at,
    })
    await broadcast({"type": "status", "status": "config_reloaded"})
    log("info", "Config saved and scheduler restarted")

    # Redirect back to /settings with success flag
    return RedirectResponse(url="/settings?saved=1", status_code=303)


# === Status endpoint ===
@app.get("/status")
async def status():
    """Status API for the dashboard."""
    async with cfg_lock:
        local_cfg = cfg

    # Resolve save path from config and env overrides
    save_path = resolve_save_dir(getattr(local_cfg, "save_path", None))

    count = 0
    last_snapshot_ts = None
    last_snapshot_full = None
    latest_mtime = None
    allowed_suffixes = ('.jpg', '.jpeg', '.png')
    if save_path.exists():
        for f in save_path.iterdir():
            if f.is_file() and f.suffix.lower() in allowed_suffixes:
                count += 1
                mtime = f.stat().st_mtime
                if latest_mtime is None or mtime > latest_mtime:
                    latest_mtime = mtime
        if latest_mtime:
            latest_dt = datetime.fromtimestamp(latest_mtime)
            last_snapshot_ts = latest_dt.strftime("%H:%M:%S")
            last_snapshot_full = latest_dt.strftime("%d.%m.%y %H:%M")
    else:
        log("warn", f"Save path does not exist: {save_path}")

    if getattr(local_cfg, "use_astral", False):
        sunrise_time, sunset_time = get_sun_times(local_cfg)
        sunrise_str = sunrise_time.strftime("%H:%M") if sunrise_time else "--:--"
        sunset_str = sunset_time.strftime("%H:%M") if sunset_time else "--:--"
    else:
        sunrise_str = "--:--"
        sunset_str = "--:--"

    # Use the same logic as the scheduler, including active weekdays
    active = is_active_time(local_cfg)

    from app.scheduler import is_paused as scheduler_paused
    return {
        "time": datetime.now().strftime("%H:%M:%S"),
        "active": active,
        "paused": bool(scheduler_paused),
        "sunrise": sunrise_str,
        "sunset": sunset_str,
        "count": count,
        "last_snapshot": last_snapshot_ts,
        "last_snapshot_tooltip": last_snapshot_full,
        "camera_error": get_camera_error(),
        "camera_health": get_camera_health(),
    }


# === Action routes ===
@app.post("/action/pause")
async def action_pause():
    await set_paused(True)
    await broadcast({"type": "status", "status": "paused"})
    return {"ok": True}


@app.post("/action/resume")
async def action_resume():
    await set_paused(False)
    await broadcast({"type": "status", "status": "running"})
    return {"ok": True}


@app.post("/action/snapshot")
async def action_snapshot():
    async with cfg_lock:
        local_cfg = cfg
    result = take_snapshot(local_cfg)
    if result:
        clear_camera_error()
        stats = get_image_stats() or {}
        count = int(stats.get("count") or 0) + 1
        set_image_stats(count, result["timestamp"], result.get("timestamp_full"))
        await broadcast({
            "type": "snapshot",
            "filename": result["filename"],
            "timestamp": result["timestamp"],
            "timestamp_full": result.get("timestamp_full")
        })
        return {"ok": True}
    else:
        set_camera_error("snapshot_failed", "Snapshot failed")
        await broadcast({
            "type": "camera_error",
            "code": "snapshot_failed",
            "message": "Snapshot failed"
        })
        return {"ok": False}


# === App lifecycle ===
@app.on_event("startup")
def startup_event():
    log("info", "Starting ChronoCam ...")
    start_scheduler()


@app.on_event("shutdown")
def shutdown_event():
    log("info", "Stopping ChronoCam ...")
    stop_scheduler()
