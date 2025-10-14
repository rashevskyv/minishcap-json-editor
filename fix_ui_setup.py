#!/usr/bin/env python3
"""
Script to fix ui/ui_setup.py and add project menu items.
This fixes the file duplication issue and adds project management to the menu.
"""

import os
import sys

def fix_ui_setup():
    file_path = "ui/ui_setup.py"

    if not os.path.exists(file_path):
        print(f"Error: {file_path} not found!")
        return False

    print(f"Reading {file_path}...")
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    print(f"Original file has {len(lines)} lines")

    # Find where duplication starts (look for second occurrence of "# --- START OF FILE")
    duplication_start = None
    for i, line in enumerate(lines):
        if i > 100 and "# --- START OF FILE" in line:
            duplication_start = i
            print(f"Found duplication at line {i+1}")
            break

    if duplication_start:
        # Remove everything from duplication point onwards
        lines = lines[:duplication_start]
        print(f"Removed duplication. New length: {len(lines)} lines")

    # Now find the menu section and replace it
    menu_start = None
    menu_end = None

    for i, line in enumerate(lines):
        if "main_window.open_action = QAction(open_icon," in line:
            menu_start = i
            print(f"Found menu start at line {i+1}")
        if menu_start and not menu_end and "file_menu.addSeparator()" in line and i > menu_start:
            # Find the first separator after open actions
            if i - menu_start < 5:  # Should be close
                menu_end = i + 1
                print(f"Found menu end at line {i+1}")
                break

    if menu_start and menu_end:
        # Replace old menu items with new project-based ones
        new_menu_code = [
            "    # Project actions\n",
            "    main_window.new_project_action = QAction(QIcon.fromTheme(\"document-new\"), '&New Project...', main_window)\n",
            "    main_window.new_project_action.setShortcut('Ctrl+N')\n",
            "    file_menu.addAction(main_window.new_project_action)\n",
            "\n",
            "    main_window.open_project_action = QAction(open_icon, '&Open Project...', main_window)\n",
            "    main_window.open_project_action.setShortcut('Ctrl+O')\n",
            "    file_menu.addAction(main_window.open_project_action)\n",
            "\n",
            "    main_window.close_project_action = QAction('&Close Project', main_window)\n",
            "    main_window.close_project_action.setEnabled(False)  # Enabled when project is loaded\n",
            "    file_menu.addAction(main_window.close_project_action)\n",
            "    file_menu.addSeparator()\n",
            "\n",
            "    # Block actions (enabled only when project is open)\n",
            "    main_window.import_block_action = QAction(QIcon.fromTheme(\"document-import\"), '&Import Block...', main_window)\n",
            "    main_window.import_block_action.setEnabled(False)  # Enabled when project is loaded\n",
            "    file_menu.addAction(main_window.import_block_action)\n",
            "    file_menu.addSeparator()\n",
        ]

        # Replace
        lines = lines[:menu_start] + new_menu_code + lines[menu_end:]
        print("Replaced old menu with project menu")

    # Write back
    print(f"Writing fixed file ({len(lines)} lines)...")
    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(lines)

    print(f"✓ Successfully fixed {file_path}")
    return True

if __name__ == "__main__":
    if fix_ui_setup():
        print("\nFile fixed successfully!")
        print("Next: Run the app with 'python main.py'")
        sys.exit(0)
    else:
        print("\nFailed to fix file!")
        sys.exit(1)
