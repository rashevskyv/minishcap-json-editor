
from utils.utils import calculate_string_width
font_map = {'{PLAYER}': {'width': 56}}
res = calculate_string_width('{PLAYER} test', font_map)
with open('test_res.txt', 'w') as f:
    f.write('Width: ' + str(res))

