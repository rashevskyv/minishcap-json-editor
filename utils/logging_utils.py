import logging
import os

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
log_file_path = os.path.join(project_root, 'app_debug.txt')

logger = logging.getLogger("app_logger")

if not logger.handlers:
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(module)s - %(funcName)s - %(message)s')
    
    # Використовуємо 'w' режим, щоб файл очищався при кожному запуску
    fh = logging.FileHandler(log_file_path, mode='w', encoding='utf-8')
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(formatter)
    # Для консолі також можна спробувати встановити кодування, хоча це залежить від терміналу
    # У VSCode це зазвичай працює добре
    ch.stream.reconfigure(encoding='utf-8')
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