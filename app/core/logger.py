import logging
from colorlog import ColoredFormatter
from app.core.settings import settings

LOG_FORMAT = (
    "%(log_color)s[%(asctime)s] [%(levelname)-8s] "
    "%(reset)s%(blue)s%(name)s:%(reset)s %(message)s"
)

formatter = ColoredFormatter(
    LOG_FORMAT,
    datefmt="%Y-%m-%d %H:%M:%S",
    reset=True,
    log_colors={
        "DEBUG": "cyan",
        "INFO": "green",
        "WARNING": "yellow",
        "ERROR": "red",
        "CRITICAL": "bold_red",
    },
)

handler = logging.StreamHandler()
handler.setFormatter(formatter)

logger = logging.getLogger("garcold")
logger.setLevel(settings.LOG_LEVEL.upper())
logger.addHandler(handler)
logger.propagate = False