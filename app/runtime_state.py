"""Holds runtime global state (e.g., last camera error)."""

from typing import Optional, Dict, Any

_camera_error: Optional[Dict[str, Any]] = None


def set_camera_error(code: Optional[str], message: str) -> None:
    """Store the last camera error."""
    global _camera_error
    _camera_error = {
        "code": code,
        "message": message
    }


def clear_camera_error() -> None:
    """Clear the stored camera error."""
    global _camera_error
    _camera_error = None


def get_camera_error() -> Optional[Dict[str, Any]]:
    """Return the last camera error if present."""
    return _camera_error
