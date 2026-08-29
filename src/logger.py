import structlog
import logging
import os
import sys
from logging.handlers import RotatingFileHandler


def setup_logging(level: str = "INFO", log_dir: str = "logs"):
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    os.makedirs(log_dir, exist_ok=True)

    console_handler = logging.StreamHandler(sys.stdout)
    file_handler = RotatingFileHandler(
        os.path.join(log_dir, "bridge.log"),
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    for handler in (console_handler, file_handler):
        handler.setFormatter(logging.Formatter("%(message)s"))

    logging.basicConfig(handlers=[console_handler, file_handler], level=level)


logger = structlog.get_logger()
