import logging
import os

# Determine the project root directory (assuming utils is one level down from project root)
# __file__ is d:\git\dev\zeldamc\jsonreader\utils\logging_utils.py
# os.path.dirname(__file__) is d:\git\dev\zeldamc\jsonreader\utils
# os.path.dirname(os.path.dirname(__file__)) is d:\git\dev\zeldamc\jsonreader
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
log_file_path = os.path.join(project_root, 'app_debug.log')

# Configure logging
# Ensure the handler is added only once to avoid duplicate logs if this module is imported multiple times
logger = logging.getLogger("app_logger") # Use a specific logger name

if not logger.handlers: # Check if handlers are already configured
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(module)s - %(funcName)s - %(message)s')
    
    # File handler
    fh = logging.FileHandler(log_file_path)
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    
    # Console handler (optional, for also printing to console)
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(formatter)
    logger.addHandler(ch)

def log_debug(message: str):
    """Logs a debug message."""
    logger.debug(message)

def log_info(message: str):
    """Logs an info message."""
    logger.info(message)

def log_warning(message: str):
    """Logs a warning message."""
    logger.warning(message)

def log_error(message: str, exc_info=False):
    """Logs an error message."""
    logger.error(message, exc_info=exc_info)

if __name__ == '__main__':
    # Example usage
    log_debug("This is a test debug message from logging_utils.py.")
    log_info("This is a test info message from logging_utils.py.")
    try:
        1 / 0
    except ZeroDivisionError:
        log_error("A ZeroDivisionError occurred.", exc_info=True)