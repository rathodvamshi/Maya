import logging

# Create a logger for the app
logger = logging.getLogger("app_logger")
logger.setLevel(logging.INFO)

# Console handler with a simple format
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s %(message)s"))
logger.addHandler(console_handler)
