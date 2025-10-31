from datetime import date, datetime, time as dtime
from typing import Optional, Tuple

from astral import LocationInfo
from astral.sun import sun

from app.logger_utils import log


def get_sun_times(cfg, target_date: Optional[date] = None) -> Tuple[Optional[dtime], Optional[dtime]]:
    """
    Berechnet Sonnenaufgang/-untergang für die in cfg gesetzte Location.
    Gibt (sunrise_time, sunset_time) als naive time-Objekte zurück (HH:MM:SS).
    """
    if target_date is None:
        target_date = date.today()

    try:
        city = LocationInfo("", "", cfg.city_tz, cfg.city_lat, cfg.city_lon)
        s = sun(city.observer, date=target_date, tzinfo=city.timezone)
        sunrise = s.get("sunrise")
        sunset = s.get("sunset")
        if sunrise and sunset:
            return sunrise.time(), sunset.time()
        return None, None
    except Exception as e:
        log("warn", f"Astral-Berechnung fehlgeschlagen: {e}")
        return None, None


def is_within_time_range(start: dtime, end: dtime, now: Optional[dtime] = None) -> bool:
    """
    Prüft, ob 'now' zwischen start und end liegt. Unterstützt Zeitfenster über Mitternacht.
    """
    if now is None:
        now = datetime.now().time()

    if start < end:
        return start <= now <= end
    else:
        # Über Mitternacht (z. B. 22:00 - 06:00)
        return now >= start or now <= end
