"""Hält zur Laufzeit globale Zustände (z. B. letzte Kamera-Fehler)."""

from typing import Optional, Dict, Any

_camera_error: Optional[Dict[str, Any]] = None


def set_camera_error(code: Optional[str], message: str) -> None:
    """Speichert den letzten Kamera-Fehler."""
    global _camera_error
    _camera_error = {
        "code": code,
        "message": message
    }


def clear_camera_error() -> None:
    """Entfernt den gespeicherten Kamera-Fehler."""
    global _camera_error
    _camera_error = None


def get_camera_error() -> Optional[Dict[str, Any]]:
    """Gibt den letzten Kamera-Fehler (falls vorhanden) zurück."""
    return _camera_error
