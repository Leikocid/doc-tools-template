# Инструментарий для работы с документами

Этот шаблон содержит инструменты для работы с документами в форматах Markdown, HTML, PDF и DOCX.

## Возможности

- Консолидация Markdown файлов в один документ
- Конвертация MD → DOCX
- Конвертация PDF → MD
- Генерация оглавления

## Структура проекта

- `sources/` - исходные документы в формате Markdown
- `generated/` - сгенерированные документы в различных форматах
- `build.py` - основной скрипт для сборки и конвертации документов
- `.vscode/tasks.json` - настройки задач VS Code

## Установка

1. Клонируйте репозиторий
2. Создайте виртуальное окружение Python:
   ```
   python -m venv .venv
   ```
3. Активируйте виртуальное окружение:
   - Windows: `.venv\Scripts\activate`
   - macOS/Linux: `source .venv/bin/activate`
4. Установите зависимости:
   ```
   pip install -r requirements.txt
   ```

## Использование

### Сборка всех документов

```
python build.py
```

### Конвертация MD → DOCX

```
python build.py --convert2docx path/to/file.md
```

### Конвертация PDF → MD

```
python build.py --convert2md path/to/file.pdf
```

## VS Code интеграция

Для VS Code доступны готовые задачи:
- Сборка документации (Ctrl+Shift+B)
- MD → DOCX (текущий файл)
- PDF → MD (текущий файл) 