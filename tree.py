import os

EXCLUDE_FILES = {'tree.py', 'tree.txt', '.gitignore'}
EXCLUDE_DIRS = {'__pycache__', '.git', 'fonts'}

def tree(dir_path, prefix="", log_file=None, is_last=True, root=True):
    entries = [e for e in os.listdir(dir_path) if e not in EXCLUDE_FILES and e not in EXCLUDE_DIRS]
    entries = sorted(entries, key=lambda x: (not os.path.isdir(os.path.join(dir_path, x)), x.lower()))
    for idx, entry in enumerate(entries):
        path = os.path.join(dir_path, entry)
        connector = "└── " if idx == len(entries) - 1 else "├── "
        line = ("" if root else prefix) + connector + entry
        if log_file:
            log_file.write(line + "\n")
        if os.path.isdir(path):
            extension = "    " if idx == len(entries) - 1 else "│   "
            tree(path, prefix + extension, log_file, idx == len(entries) - 1, False)

if __name__ == "__main__":
    root_dir = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(root_dir, "tree.txt"), "w", encoding="utf-8") as log:
        tree(root_dir, log_file=log)