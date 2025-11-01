from fastapi import FastAPI, Request, Form
from typing import List
from fastapi.responses import HTMLResponse, StreamingResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
import asyncio
import json
from datetime import datetime

from app.config_manager import load_config, save_config
from app.models import ConfigModel
from app.scheduler import start_scheduler, stop_scheduler, cfg_lock, cfg, set_paused
from app import i18n
from app.broadcast_manager import clients, broadcast
from app.logger_utils import log
from app.downloader import take_snapshot
from app.sunrise_utils import get_sun_times, is_within_time_range

# === FastAPI App ===
app = FastAPI()

# === Static Mount (CSS, JS, Bilder) ===
app.mount(
    "/static",
    StaticFiles(directory=Path(__file__).parent / "static"),
    name="static"
)

# === Templates ===
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


# === SSE: Server-Sent Events für Live-Updates ===
@app.get("/events")
async def sse_events():
    """SSE-Endpunkt für Dashboard-Updates (Snapshots, Status etc.)."""
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


# === Index-Seite ===
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    async with cfg_lock:
        local_cfg = cfg

    # Cache-Buster für last.jpg, damit sofort das aktuelle Bild geladen wird
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


# === Settings-Seite ===
@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    """Zeigt Einstellungsseite (dein Original-Layout)."""
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


# === Einstellungen speichern ===
@app.post("/update", response_class=HTMLResponse)
async def update_settings(
    request: Request,
    CAM_URL: str = Form(...),
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
    """Speichert Settings und leitet mit Erfolgsparameter zurück zu /settings."""
    async with cfg_lock:
        cfg.cam_url = CAM_URL
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
    await broadcast({"type": "status", "status": "config_reloaded"})
    log("info", "Konfiguration gespeichert und Scheduler neu gestartet")

    # Redirect zurück zu /settings mit Erfolgsparameter
    return RedirectResponse(url="/settings?saved=1", status_code=303)


# === Status-Endpunkt ===
@app.get("/status")
async def status():
    """Status-API fürs Dashboard."""
    async with cfg_lock:
        local_cfg = cfg

    app_dir = Path(__file__).resolve().parent
    save_path = (app_dir / local_cfg.save_path).resolve()

    count = 0
    if save_path.exists():
        count = len([
            f for f in save_path.iterdir()
            if f.is_file() and f.suffix.lower() in ('.jpg', '.jpeg', '.png')
        ])
    else:
        log("warn", f"Speicherpfad existiert nicht: {save_path}")

    if getattr(local_cfg, "use_astral", False):
        sunrise_time, sunset_time = get_sun_times(local_cfg)
        sunrise_str = sunrise_time.strftime("%H:%M") if sunrise_time else "--:--"
        sunset_str = sunset_time.strftime("%H:%M") if sunset_time else "--:--"
    else:
        sunrise_str = "--:--"
        sunset_str = "--:--"

    try:
        cfg_start = datetime.strptime(local_cfg.active_start, "%H:%M").time()
        cfg_end = datetime.strptime(local_cfg.active_end, "%H:%M").time()
    except Exception:
        cfg_start = datetime.strptime("00:00", "%H:%M").time()
        cfg_end = datetime.strptime("23:59", "%H:%M").time()

    active = is_within_time_range(cfg_start, cfg_end)
    if getattr(local_cfg, "use_astral", False) and sunrise_time and sunset_time:
        active = active and is_within_time_range(sunrise_time, sunset_time)

    from app.scheduler import is_paused as scheduler_paused
    return {
        "time": datetime.now().strftime("%H:%M:%S"),
        "active": active,
        "paused": bool(scheduler_paused),
        "sunrise": sunrise_str,
        "sunset": sunset_str,
        "count": count
    }


# === Action-Routen ===
@app.post("/action/pause")
async def action_pause():
    set_paused(True)
    await broadcast({"type": "status", "status": "paused"})
    return {"ok": True}


@app.post("/action/resume")
async def action_resume():
    set_paused(False)
    await broadcast({"type": "status", "status": "running"})
    return {"ok": True}


@app.post("/action/snapshot")
async def action_snapshot():
    async with cfg_lock:
        local_cfg = cfg
    result = take_snapshot(local_cfg)
    if result:
        await broadcast({
            "type": "snapshot",
            "filename": result["filename"],
            "timestamp": result["timestamp"]
        })
        return {"ok": True}
    else:
        await broadcast({
            "type": "camera_error",
            "message": "Snapshot fehlgeschlagen"
        })
        return {"ok": False}


# === App-Lifecycle ===
@app.on_event("startup")
def startup_event():
    log("info", "Starte ChronoCam ...")
    start_scheduler()


@app.on_event("shutdown")
def shutdown_event():
    log("info", "Beende ChronoCam ...")
    stop_scheduler()
