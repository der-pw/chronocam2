from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import time


class ConfigModel(BaseModel):
    """Globale App-Konfiguration (ersetzt frühere INI-Datei)"""
    cam_url: str = Field("", description="URL des Webcam-Snapshots")
    username: Optional[str] = Field(None, description="Kamera-Benutzername")
    password: Optional[str] = Field(None, description="Kamera-Passwort")
    auth_type: str = Field("none", description="Authentifizierungstyp: none/basic/digest")
    save_path: str = Field("./data", description="Pfad zum Speichern der Bilder")

    interval_seconds: int = Field(10, description="Aufnahmeintervall in Sekunden")
    active_start: str = Field("06:00", description="Startzeit (HH:MM)")
    active_end: str = Field("18:00", description="Endzeit (HH:MM)")
    active_days: List[str] = Field(default_factory=lambda: ["Mon", "Tue", "Wed", "Thu", "Fri"])

    paused: bool = Field(False, description="Scheduler-Status: pausiert ja/nein")

    use_astral: bool = Field(False, description="Sonnenauf-/untergang verwenden")
    city_lat: float = Field(52.52, description="Breitengrad")
    city_lon: float = Field(13.405, description="Längengrad")
    city_tz: str = Field("Europe/Berlin", description="Zeitzone")

    log_file: Optional[str] = Field(None, description="Logdatei (optional)")
    log_enabled: bool = Field(True, description="Write chronocam.log file")
    language: str = Field("de", description="Language code (e.g., de, en)")


class StatusModel(BaseModel):
    """Status-API-Rückgabe"""
    time: str
    active: bool
    paused: bool = False
    image_count: int = 0


class SnapshotEvent(BaseModel):
    """SSE-Ereignis (z. B. neues Bild oder Fehler)"""
    type: str
    message: Optional[str] = None
    filename: Optional[str] = None
    count: Optional[int] = None
