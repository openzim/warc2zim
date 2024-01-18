from pathlib import Path

from zimscraperlib import getLogger

LOGGER_NAME = Path(__file__).parent.name

# Shared logger with default log level at this stage
logger = getLogger(LOGGER_NAME)
