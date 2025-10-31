import requests
from requests.auth import HTTPBasicAuth, HTTPDigestAuth
from datetime import datetime
from pathlib import Path
import shutil
from app.logger_utils import log


def take_snapshot(cfg):
    """Lädt ein Bild von der Kamera herunter und speichert es lokal."""
    if not cfg.cam_url:
        log("warn", "Keine Kamera-URL gesetzt – Snapshot übersprungen.")
        return None

    try:
        save_dir = Path(cfg.save_path)
        save_dir.mkdir(parents=True, exist_ok=True)

        now = datetime.now()
        filename = f"snapshot_{now.strftime('%Y%m%d_%H%M%S')}.jpg"
        filepath = save_dir / filename

        # Authentifizierung
        auth = None
        if cfg.auth_type == "basic" and cfg.username and cfg.password:
            auth = HTTPBasicAuth(cfg.username, cfg.password)
            log("info", "Verwende HTTP Basic Auth.")
        elif cfg.auth_type == "digest" and cfg.username and cfg.password:
            auth = HTTPDigestAuth(cfg.username, cfg.password)
            log("info", "Verwende HTTP Digest Auth.")
        else:
            log("info", "Keine Authentifizierung verwendet.")

        # Snapshot laden
        log("info", f"Lade Snapshot von {cfg.cam_url} ...")
        resp = requests.get(cfg.cam_url, auth=auth, timeout=10)

        if resp.status_code != 200:
            log("error", f"Kamera antwortete mit Status {resp.status_code}")
            return None

        # Datei speichern
        with open(filepath, "wb") as f:
            f.write(resp.content)

        log("info", f"Snapshot gespeichert: {filename}")

        # Kopie nach app/static/img/last.jpg für Dashboard
        try:
            preview_path = Path(__file__).resolve().parent / "static" / "img" / "last.jpg"
            preview_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(filepath, preview_path)
            log("info", f"last.jpg aktualisiert ({preview_path})")
        except Exception as e:
            log("error", f"Fehler beim Kopieren von last.jpg: {e}")

        return {
            "filename": filename,
            "filepath": str(filepath),
            "timestamp": now.strftime("%H:%M:%S")
        }

    except Exception as e:
        log("error", f"Snapshot fehlgeschlagen: {e}")
        return None
