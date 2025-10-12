# --- START OF FILE utils/logging_utils.py ---
import logging
import os
import time
from collections import deque

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
log_file_path = os.path.join(project_root, 'app_debug.txt')


class DuplicateFilter(logging.Filter):
    """
    Filter that suppresses duplicate log messages that occur within a short time window.
    This prevents log spam from repeated identical messages.
    """
    def __init__(self, time_window=0.5, max_history=100):
        """
        Args:
            time_window: Time window in seconds to consider messages as duplicates (default 0.5s)
            max_history: Maximum number of recent messages to track (default 100)
        """
        super().__init__()
        self.time_window = time_window
        self.max_history = max_history
        # Store tuples of (message, timestamp)
        self.recent_messages = deque(maxlen=max_history)

    def filter(self, record):
        """
        Determine if a log record should be logged or filtered out.
        Returns True to log, False to suppress.
        """
        current_time = time.time()
        message = record.getMessage()

        # Clean up old messages outside the time window
        while self.recent_messages and (current_time - self.recent_messages[0][1]) > self.time_window:
            self.recent_messages.popleft()

        # Check if this message was logged recently
        for recent_msg, recent_time in self.recent_messages:
            if recent_msg == message and (current_time - recent_time) < self.time_window:
                # Duplicate message within time window - suppress it
                return False

        # New message or outside time window - log it and remember it
        self.recent_messages.append((message, current_time))
        return True


logger = logging.getLogger("app_logger")

if not logger.handlers:
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(module)s - %(funcName)s - %(message)s')

    # Create duplicate filter to prevent log spam
    duplicate_filter = DuplicateFilter(time_window=0.5, max_history=100)

    # Використовуємо 'w' режим, щоб файл очищався при кожному запуску
    fh = logging.FileHandler(log_file_path, mode='w', encoding='utf-8')
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(formatter)
    fh.addFilter(duplicate_filter)  # Add filter to file handler
    logger.addHandler(fh)

    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(formatter)
    # Для консолі також можна спробувати встановити кодування, хоча це залежить від терміналу
    # У VSCode це зазвичай працює добре
    ch.stream.reconfigure(encoding='utf-8')
    ch.addFilter(duplicate_filter)  # Add filter to console handler
    logger.addHandler(ch)

def log_debug(message: str):
    logger.debug(message)

def log_info(message: str):
    logger.info(message)

def log_warning(message: str):
    logger.warning(message)

def log_error(message: str, exc_info=False):
    logger.error(message, exc_info=exc_info)

if __name__ == '__main__':
    log_debug("This is a test debug message from logging_utils.py.")
    log_info("This is a test info message from logging_utils.py.")
    try:
        1 / 0
    except ZeroDivisionError:
        log_error("A ZeroDivisionError occurred.", exc_info=True)