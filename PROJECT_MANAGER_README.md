# ProjectManager Implementation

## Огляд

Реалізовано перший етап з `PLAN.md`: **Закладення фундаменту - Моделі даних та управління проектами**.

## Що реалізовано

### 1. Моделі даних (`core/project_manager.py`)

#### `Category` (Категорія)
- Віртуальна група рядків всередині блоку
- Підтримує ієрархічну структуру (parent/children)
- Зберігає індекси рядків (`line_indices`)
- Має метадані: назва, опис, колір для UI
- Методи:
  - `add_child()` - додати дочірню категорію
  - `remove_child()` - видалити дочірню категорію
  - `find_category()` - рекурсивний пошук за ID
  - `to_dict()` / `from_dict()` - серіалізація в JSON

#### `Block` (Блок)
- Представляє пару файлів (source/translation)
- Містить список кореневих категорій
- Зберігає метадані блоку
- Методи:
  - `add_category()` / `remove_category()` - управління категоріями
  - `find_category()` - пошук категорії за ID
  - `get_all_categories_flat()` - отримати всі категорії плоским списком
  - `get_categorized_line_indices()` - отримати всі індекси, що належать категоріям
  - `to_dict()` / `from_dict()` - серіалізація в JSON

#### `Project` (Проект)
- Контейнер верхнього рівня
- Містить список блоків
- Зберігає назву активного плагіна
- Має timestamps (created_at, modified_at)
- Методи:
  - `add_block()` / `remove_block()` - управління блоками
  - `find_block()` / `find_block_by_name()` - пошук блоків
  - `to_dict()` / `from_dict()` - серіалізація в JSON

### 2. ProjectManager (Менеджер проектів)

Основний клас для роботи з проектами.

#### Структура проекту на диску:
```
project_folder/
    project.uiproj          # Файл метаданих проекту
    sources/                # Вихідні файли (оригінали)
        file1.txt
        file2.txt
    translation/            # Файли перекладів
        file1.txt
        file2.txt
```

#### Методи:

**`create_new_project(project_dir, name, plugin_name, description="")`**
- Створює нову структуру проекту на диску
- Ініціалізує metadata файл `.uiproj`
- Створює теки `sources/` та `translation/`

**`load(path)`**
- Завантажує існуючий проект
- Приймає шлях до теки проекту або файлу `.uiproj`
- Парсить JSON та відновлює структуру даних

**`save()`**
- Зберігає поточний проект на диск
- Оновлює timestamp `modified_at`
- Серіалізує всю структуру в JSON

**`add_block(name, source_file_path, description="")`**
- Імпортує новий блок (файл) в проект
- Копіює source файл в `sources/`
- Створює порожній файл перекладу в `translation/`
- Повертає об'єкт `Block`

**`get_uncategorized_lines(block_id, total_lines)`**
- Обчислює індекси рядків, що не належать жодній категорії
- Використовується для автоматичного вузла "Uncategorized" в UI

**`get_absolute_path(relative_path)` / `get_relative_path(absolute_path)`**
- Конвертація між абсолютними та відносними шляхами в проекті

## Тестування

### Юніт-тести (`test_project_manager.py`)

Створено 6 тестів, що перевіряють:

1. **test_basic_project_creation** - створення нового проекту
2. **test_load_save_project** - завантаження та збереження
3. **test_add_block** - додавання блоку з копіюванням файлів
4. **test_categories** - управління категоріями та ієрархією
5. **test_uncategorized_lines** - обчислення некатегоризованих рядків
6. **test_serialization** - JSON серіалізація/десеріалізація

Запуск тестів:
```bash
python test_project_manager.py
```

Результат: **✓ All tests passed!**

### Демонстрація (`demo_project.py`)

Створено інтерактивну демонстрацію, що показує:

1. **Сценарій 1** - Створення та наповнення проекту (з PLAN.md)
2. **Сценарій 2** - Організація роботи за допомогою категорій
3. **Сценарій 3** - Робота з контекстним перекладом
4. **Бонус** - Візуалізація автоматичного вузла "Uncategorized"

Запуск демо:
```bash
python demo_project.py
```

## Використання

### Приклад: Створення нового проекту

```python
from core.project_manager import ProjectManager

# Створити новий проект
manager = ProjectManager()
manager.create_new_project(
    project_dir="D:/Translation/MyProject",
    name="My Translation Project",
    plugin_name="zelda_mc",
    description="Translation of Zelda: Minish Cap"
)

# Додати блок
block = manager.add_block(
    name="Main Dialogs",
    source_file_path="C:/original_messages.txt",
    description="Main game dialogs"
)

# Зберегти проект
manager.save()
```

### Приклад: Робота з категоріями

```python
from core.project_manager import Category

# Створити категорію
category = Category(
    name="NPC Dialogs",
    description="All NPC dialogs in town",
    line_indices=[0, 1, 2, 3, 4, 5]
)

# Додати підкатегорію
subcategory = Category(
    name="Shop Keeper",
    description="Shop keeper dialogs",
    line_indices=[0, 1]
)
category.add_child(subcategory)

# Додати до блоку
block.add_category(category)

# Зберегти
manager.save()
```

### Приклад: Завантаження проекту

```python
# Завантажити існуючий проект
manager = ProjectManager()
manager.load("D:/Translation/MyProject")

# Отримати інформацію
print(f"Project: {manager.project.name}")
print(f"Plugin: {manager.project.plugin_name}")
print(f"Blocks: {len(manager.project.blocks)}")

# Знайти блок
block = manager.project.find_block_by_name("Main Dialogs")

# Отримати некатегоризовані рядки
uncategorized = manager.get_uncategorized_lines(block.id, total_lines=100)
print(f"Uncategorized lines: {uncategorized}")
```

## Наступні кроки

Відповідно до PLAN.md, наступні етапи:

### Етап 2: Перехід на проектний підхід - UI для управління проектами
- Створити діалоги для створення/відкриття проектів
- Оновити меню "Файл"
- Адаптувати `AppActionHandler` для роботи з проектами

### Етап 3: Візуалізація ієрархії - Дерево блоків та категорій
- Замінити `QListWidget` на `QTreeWidget`
- Реалізувати Drag-and-Drop для призначення рядків категоріям
- Створити `ProjectTreeView` компонент

### Етап 4: Управління елементами
- Універсальний діалог властивостей для блоків та категорій
- Контекстні меню для роботи з деревом

### Етап 5-7: Інтеграція та завершення
- Множинне виділення у прев'ю (вже реалізовано)
- Діалог управління категоріями
- Адаптація фільтрації та перекладу для роботи з категоріями

## Технічні деталі

### Серіалізація

Проект зберігається у форматі JSON з наступною структурою:

```json
{
  "id": "uuid",
  "name": "Project Name",
  "description": "...",
  "plugin_name": "zelda_mc",
  "version": "1.0",
  "created_at": "2025-10-13T...",
  "modified_at": "2025-10-13T...",
  "blocks": [
    {
      "id": "uuid",
      "name": "Block Name",
      "source_file": "sources/file.txt",
      "translation_file": "translation/file.txt",
      "description": "...",
      "categories": [
        {
          "id": "uuid",
          "name": "Category Name",
          "description": "...",
          "line_indices": [0, 1, 2],
          "children": [...],
          "parent_id": "uuid or null",
          "color": "#FF0000"
        }
      ],
      "metadata": {}
    }
  ],
  "metadata": {}
}
```

### UUID для ідентифікації

Всі об'єкти (Project, Block, Category) мають унікальний UUID, що дозволяє:
- Надійно посилатися на об'єкти
- Переміщувати категорії в ієрархії
- Уникати конфліктів при рефакторингу

### Відносні шляхи

Файли в проекті зберігаються з відносними шляхами, що робить проект портативним:
- Можна переміщувати теку проекту
- Легко працювати з Git
- Простіше шарити проекти між користувачами

## Сумісність

Реалізація повністю сумісна з існуючим кодом:
- Використовує ті ж утиліти логування (`utils.logging_utils`)
- Не змінює існуючі модулі
- Готова до інтеграції з `MainWindow` та хендлерами

## Статус

**Етап 1 завершено**: ✅ Закладено фундамент моделей даних та управління проектами

Готово до переходу до **Етапу 2**: Створення UI для управління проектами.
