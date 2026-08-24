import logging
import sys

logger = logging.getLogger("vera")
logger.setLevel(logging.INFO)

if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        '{"time":"%(asctime)s", "level":"%(levelname)s", "module":"%(name)s", "message":"%(message)s"}'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
