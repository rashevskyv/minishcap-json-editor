#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Demo script showing how to use the ProjectManager.
This demonstrates the workflow described in PLAN.md.
"""

import os
import sys
import io
import tempfile
from pathlib import Path

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.project_manager import ProjectManager, Category


def demo_scenario_1():
    """
    Scenario 1 from PLAN.md: Creating and populating a project
    """
    print("=" * 70)
    print("Scenario 1: Creating and Populating a Project")
    print("=" * 70)
    print()

    with tempfile.TemporaryDirectory() as temp_dir:
        # Step 1: User creates a new project
        print("Step 1: User creates new project 'Wind Waker Translation'")
        project_dir = os.path.join(temp_dir, "ZeldaWW")

        manager = ProjectManager()
        manager.create_new_project(
            project_dir=project_dir,
            name="Переклад Wind Waker",
            plugin_name="zelda_ww",
            description="Повний переклад The Legend of Zelda: The Wind Waker"
        )

        print(f"   ✓ Project created at: {project_dir}")
        print(f"   ✓ Plugin: {manager.project.plugin_name}")
        print()

        # Step 2: Create a sample source file
        print("Step 2: Creating sample source file 'message_orig.txt'")
        source_file = os.path.join(temp_dir, "message_orig.txt")
        with open(source_file, 'w', encoding='utf-8') as f:
            # Simulate game text with multiple lines
            for i in range(100):
                if i < 10:
                    f.write(f"Dialog line {i}: Welcome to Outset Island!\n")
                elif i < 50:
                    f.write(f"Dialog line {i}: This is a quest dialog.\n")
                else:
                    f.write(f"Dialog line {i}: Shop keeper message.\n")

        print(f"   ✓ Created source file with 100 lines")
        print()

        # Step 3: Import block
        print("Step 3: Importing block into project")
        block = manager.add_block(
            name="Main Messages",
            source_file_path=source_file,
            description="Main game dialog messages"
        )

        print(f"   ✓ Block '{block.name}' added to project")
        print(f"   ✓ Block ID: {block.id}")
        print()

        return manager, block


def demo_scenario_2(manager, block):
    """
    Scenario 2 from PLAN.md: Organizing work with categories
    """
    print("=" * 70)
    print("Scenario 2: Organizing Work with Categories")
    print("=" * 70)
    print()

    # Step 1: Create categories for different dialog groups
    print("Step 1: Creating categories for organizing dialogs")

    # Category 1: Outset Island dialogs (lines 0-9)
    outset_island = Category(
        name="Outset Island Dialogs",
        description="Діалоги на стартовому острові до отримання меча",
        line_indices=list(range(0, 10))
    )

    # Category 2: Quest dialogs (lines 10-49)
    quest_dialogs = Category(
        name="Quest Dialogs",
        description="Діалоги квестів у грі",
        line_indices=list(range(10, 50))
    )

    # Category 3: Shop messages (lines 50-99)
    shop_messages = Category(
        name="Shop Messages",
        description="Повідомлення від торговців",
        line_indices=list(range(50, 100))
    )

    # Add categories to block
    block.add_category(outset_island)
    block.add_category(quest_dialogs)
    block.add_category(shop_messages)

    print(f"   ✓ Created category '{outset_island.name}' (lines: {len(outset_island.line_indices)})")
    print(f"   ✓ Created category '{quest_dialogs.name}' (lines: {len(quest_dialogs.line_indices)})")
    print(f"   ✓ Created category '{shop_messages.name}' (lines: {len(shop_messages.line_indices)})")
    print()

    # Step 2: Create hierarchical subcategory
    print("Step 2: Creating subcategory within 'Outset Island Dialogs'")

    grandma_dialogs = Category(
        name="Grandma Dialogs",
        description="Діалоги бабусі",
        line_indices=[0, 1, 2]  # Subset of Outset Island
    )

    outset_island.add_child(grandma_dialogs)

    print(f"   ✓ Created subcategory '{grandma_dialogs.name}' under '{outset_island.name}'")
    print(f"   ✓ Subcategory contains {len(grandma_dialogs.line_indices)} lines")
    print()

    # Step 3: Show category statistics
    print("Step 3: Category statistics")
    print(f"   • Total categories: {len(block.get_all_categories_flat())}")
    print(f"   • Root categories: {len(block.categories)}")
    print(f"   • Categorized lines: {len(block.get_categorized_line_indices())}")
    print(f"   • Uncategorized lines: {len(manager.get_uncategorized_lines(block.id, 100))}")
    print()

    # Save project
    manager.save()
    print("   ✓ Project saved with categories")
    print()


def demo_scenario_3(manager, block):
    """
    Scenario 3 from PLAN.md: Context translation (demonstration of data structure)
    """
    print("=" * 70)
    print("Scenario 3: Context Translation Workflow")
    print("=" * 70)
    print()

    print("When user selects category 'Outset Island Dialogs':")
    print()

    # Find the category
    outset_category = None
    for cat in block.categories:
        if cat.name == "Outset Island Dialogs":
            outset_category = cat
            break

    if outset_category:
        print(f"   • Category: {outset_category.name}")
        print(f"   • Description: {outset_category.description}")
        print(f"   • Line indices to translate: {outset_category.line_indices}")
        print()
        print("The translation handler would:")
        print(f"   1. Extract ONLY lines {outset_category.line_indices} from source file")
        print(f"   2. Send these lines to AI for translation")
        print(f"   3. Write translations to corresponding lines in translation file")
        print()

        # Show subcategory workflow
        if outset_category.children:
            child = outset_category.children[0]
            print(f"If user selects subcategory '{child.name}':")
            print(f"   • Line indices to translate: {child.line_indices}")
            print(f"   • This is a focused subset of the parent category")
            print()


def demo_uncategorized_handling(manager, block):
    """
    Show how "Uncategorized" virtual node would work
    """
    print("=" * 70)
    print("Bonus: 'Uncategorized' Virtual Node")
    print("=" * 70)
    print()

    total_lines = 100
    uncategorized = manager.get_uncategorized_lines(block.id, total_lines)

    print("The tree view would automatically show:")
    print()
    print(f"  📁 {block.name}")
    print(f"     📂 Outset Island Dialogs ({len(block.categories[0].line_indices)} lines)")
    print(f"        📂 Grandma Dialogs ({len(block.categories[0].children[0].line_indices)} lines)")
    print(f"     📂 Quest Dialogs ({len(block.categories[1].line_indices)} lines)")
    print(f"     📂 Shop Messages ({len(block.categories[2].line_indices)} lines)")
    print(f"     📂 Uncategorized ({len(uncategorized)} lines) [auto-generated]")
    print()
    print(f"Lines in 'Uncategorized': {uncategorized}")
    print()


def main():
    """Run all demo scenarios."""
    print()
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 68 + "║")
    print("║" + "  ProjectManager Demo - Translation Workbench".center(68) + "║")
    print("║" + "  Based on PLAN.md scenarios".center(68) + "║")
    print("║" + " " * 68 + "║")
    print("╚" + "═" * 68 + "╝")
    print()

    # Run scenarios
    manager, block = demo_scenario_1()
    demo_scenario_2(manager, block)
    demo_scenario_3(manager, block)
    demo_uncategorized_handling(manager, block)

    print("=" * 70)
    print("Demo Complete!")
    print("=" * 70)
    print()
    print("Next steps (from PLAN.md):")
    print("  • Create UI dialogs for project management")
    print("  • Replace QListWidget with QTreeWidget")
    print("  • Implement drag-and-drop for line assignment")
    print("  • Integrate with translation handler")
    print()


if __name__ == "__main__":
    main()
