import json
from pathlib import Path
from typing import Optional
from app.models import ConfigModel

CONFIG_PATH = Path(__file__).resolve().parent / "config.json"


def load_config() -> ConfigModel:
    """Lädt config.json oder erzeugt Standardwerte."""
    if CONFIG_PATH.exists():
        try:
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            return ConfigModel(**data)
        except Exception as e:
            print(f"[WARN] Fehler beim Laden der Config: {e}")
    # Fallback auf Defaultwerte
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
