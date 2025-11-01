import json
from pathlib import Path
from typing import Optional
from app.models import ConfigModel

CONFIG_PATH = Path(__file__).resolve().parent / "/data/config.json"
DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent / "config.default.json"


def load_config() -> ConfigModel:
    """Lädt config.json; beim ersten Start aus config.default.json initialisieren.

    Reihenfolge:
    1) Wenn config.json existiert -> laden und zurückgeben
    2) Wenn nicht, aber config.default.json existiert -> Inhalt nach config.json übernehmen
    3) Fallback: Pydantic-Defaults verwenden und in config.json schreiben
    """
    # 1) Normales Laden, falls vorhanden
    if CONFIG_PATH.exists():
        try:
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            return ConfigModel(**data)
        except Exception as e:
            print(f"[WARN] Fehler beim Laden der Config: {e}")

    # 2) Erster Start: Default-Datei nach config.json kopieren, wenn möglich
    if DEFAULT_CONFIG_PATH.exists():
        try:
            default_data = json.loads(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
            CONFIG_PATH.write_text(
                json.dumps(default_data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            print("[INFO] config.default.json nach config.json kopiert")
            return ConfigModel(**default_data)
        except Exception as e:
            print(f"[WARN] Konnte Default-Konfiguration nicht übernehmen: {e}")

    # 3) Letzter Fallback: Modell-Defaults verwenden
    cfg = ConfigModel()
    save_config(cfg)
    return cfg


def save_config(cfg: ConfigModel | dict) -> None:
    """Speichert die Konfiguration in config.json."""
    if isinstance(cfg, ConfigModel):
        data = cfg.model_dump()
    else:
        data = dict(cfg)
    CONFIG_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print("[INFO] Konfiguration gespeichert:", CONFIG_PATH)

