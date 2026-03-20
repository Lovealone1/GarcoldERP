from datetime import datetime
from zoneinfo import ZoneInfo

def now_colombian_time() -> datetime:
    """Returns the current datetime in the America/Bogota timezone."""
    return datetime.now(ZoneInfo("America/Bogota"))
