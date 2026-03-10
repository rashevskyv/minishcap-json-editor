
from utils.logging_utils import log_info, update_logger_handlers, set_enabled_log_categories
set_enabled_log_categories(['general', 'ui_action'])
update_logger_handlers(True, True, 'app_debug.txt')
from utils.utils import calculate_string_width
import json
with open('plugins/pokemon_fr/font_map.json', 'r', encoding='utf-8') as f:
    d = json.load(f)
res = calculate_string_width('{PLAYER} test', d)
print('res:', res)

