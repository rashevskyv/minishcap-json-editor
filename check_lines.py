import os

def count_lines(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return len(f.readlines())
    except:
        return 0

for root, dirs, files in os.walk('.'):
    if 'venv' in dirs:
        dirs.remove('venv')
    if '.git' in dirs:
        dirs.remove('.git')
    for file in files:
        if file.endswith('.py'):
            path = os.path.join(root, file)
            lines = count_lines(path)
            if lines > 500:
                print(f"{path}: {lines} lines")
