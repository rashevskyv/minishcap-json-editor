# utils.py (без змін, але переконаймося, що використовується)
import datetime
import re

def log_debug(message):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] DEBUG: {message}") # Keep DEBUG prefix for filtering if needed

def clean_newline_at_end(text):
    if text == "\n":
        return ""
    elif text.endswith("\n"):
        cleaned_text = text[:-1]
        return cleaned_text
    return text