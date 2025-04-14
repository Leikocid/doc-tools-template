import sys
import os
import glob
import markdown
from xml.etree import ElementTree
import io
from weasyprint import HTML, CSS
from markdown.extensions.toc import slugify_unicode
import pypandoc # Импортируем pypandoc
import shutil # Для проверки наличия pandoc
import argparse # Для обработки аргументов командной строки
from PyPDF2 import PdfReader # Для работы с PDF файлами

# === Настройки цветного вывода в терминал ===
# Коды ANSI для цветного вывода
COLOR_RESET = '\033[0m'      # Сброс всех стилей
COLOR_BOLD = '\033[1m'       # Жирный текст
COLOR_RED = '\033[31m'       # Красный (для ошибок)
COLOR_GREEN = '\033[32m'     # Зеленый (для успешных операций)
COLOR_YELLOW = '\033[33m'    # Желтый (для предупреждений)
COLOR_BLUE = '\033[34m'      # Синий (для информации)
COLOR_MAGENTA = '\033[35m'   # Пурпурный (для заголовков)
COLOR_CYAN = '\033[36m'      # Голубой (для подзаголовков)

# Функции для цветного вывода
def print_header(text):
    """Печатает заголовок голубым цветом"""
    print(f"{COLOR_MAGENTA}{COLOR_BOLD}{text}{COLOR_RESET}")

def print_subheader(text):
    """Печатает подзаголовок голубым цветом"""
    print(f"{COLOR_CYAN}{COLOR_BOLD}{text}{COLOR_RESET}")

def print_info(text):
    """Печатает информационное сообщение синим цветом"""
    print(f"{COLOR_BLUE}{text}{COLOR_RESET}")

def print_success(text):
    """Печатает сообщение об успехе зеленым цветом"""
    print(f"{COLOR_GREEN}{text}{COLOR_RESET}")

def print_warning(text, file=sys.stderr):
    """Печатает предупреждение желтым цветом"""
    print(f"{COLOR_YELLOW}Предупреждение: {text}{COLOR_RESET}", file=file)

def print_error(text, file=sys.stderr):
    """Печатает сообщение об ошибке красным цветом"""
    print(f"{COLOR_RED}Ошибка: {text}{COLOR_RESET}", file=file)

# === Настройки ===
SOURCE_DIR = "sources"
GENERATED_DIR = "generated"
FONTS_DIR = "fonts" # Папка со шрифтами

# Определяем имя проекта из имени директории
script_dir = os.path.abspath(os.path.dirname(__file__))
project_name_original = os.path.basename(script_dir)
# Удаляем создание slug версии, т.к. используем оригинальное имя с пробелами/скобками

OUTPUT_FILENAME_BASE = f"{project_name_original} (Consolidated)"

OUTPUT_MD = f"{OUTPUT_FILENAME_BASE}.md"
OUTPUT_HTML = f"{OUTPUT_FILENAME_BASE}.html"
OUTPUT_PDF = f"{OUTPUT_FILENAME_BASE}.pdf"
OUTPUT_DOCX = f"{OUTPUT_FILENAME_BASE}.docx" # Новое имя файла DOCX
TOC_TITLE_MD = "# Оглавление"  # Заголовок для MD файла
TOC_MAX_DEPTH = 1

# === Вспомогательные функции ===

def extract_toc_from_html(html_toc):
    """Извлекает оглавление из HTML и форматирует в Markdown."""
    if not html_toc:
        return ""
    try:
        root = ElementTree.fromstring(f"<root>{html_toc}</root>")
        markdown_lines = []
        def parse_node(element, level=0):
            indent = "    " * level
            if element.tag == 'ul':
                for item_in_ul in element.findall('li'):
                    parse_node(item_in_ul, level)
            elif element.tag == 'li':
                link = element.find('a')
                if link is not None and 'href' in link.attrib:
                    title = link.text if link.text else ''
                    href = link.attrib['href']
                    markdown_lines.append(f"{indent}*   [{title}]({href})")
                nested_ul = element.find('ul')
                if nested_ul is not None:
                    parse_node(nested_ul, level + 1)
        toc_div = root.find(".//div[@class='toc']")
        if toc_div is not None:
            ul_element = toc_div.find('ul')
            if ul_element is not None:
                parse_node(ul_element, level=0)
        return "\n".join(markdown_lines)
    except ElementTree.ParseError as e:
        print_error(f"Ошибка парсинга HTML оглавления для MD: {e}")
        return ""
    except Exception as e:
        print_error(f"Неожиданная ошибка при обработке HTML оглавления для MD: {e}")
        return ""

def generate_md_toc_from_text(text, max_level=3):
    """Генерирует ТОЛЬКО Markdown оглавление из строки MD текста (тела документа)."""
    try:
        # Используем slugify_unicode для генерации ссылок
        md = markdown.Markdown(extensions=['toc', 'extra'], 
                               extension_configs={'toc': {
                                   'toc_depth': f'1-{max_level}',
                                   'slugify': slugify_unicode 
                               }})
        md.convert(text)
        html_toc = getattr(md, 'toc', '')
        markdown_toc_str = extract_toc_from_html(html_toc)
        return markdown_toc_str
    except Exception as e:
        print_error(f"Ошибка при генерации Markdown оглавления: {e}")
        return None

# === Основные шаги сборки ===

def create_consolidated_md(source_dir, output_path_md, toc_title, toc_max_depth):
    """Шаг 1: Читает исходники, генерирует MD ToC и сохраняет итоговый MD файл.
       Возвращает True при успехе, False при ошибке.
    """
    print_info(f"-> Проверка директории исходников '{source_dir}'...")
    if not os.path.isdir(source_dir):
        print_error(f"Директория исходных файлов '{source_dir}' не найдена.")
        return False

    print_info(f"-> Поиск и сортировка файлов в '{source_dir}'...")
    source_files = sorted(glob.glob(os.path.join(source_dir, "[0-9][0-9]_*.md")))
    consolidated_md_body_content = ""

    if not source_files:
        print_warning(f"Не найдено файлов '[0-9][0-9]_*.md' в '{source_dir}'.")
    else:
        print_info("-> Объединение исходных Markdown файлов...")
        content_buffer = io.StringIO()
        first_file = True
        for filepath in source_files:
            filename = os.path.basename(filepath)
            print_info(f"   + Добавление: {filename}")
            try:
                with open(filepath, 'r', encoding='utf-8') as infile:
                    if not first_file:
                        content_buffer.write("\n\n")
                    content_buffer.write(infile.read())
                    first_file = False
            except Exception as e:
                print_error(f"Ошибка чтения файла '{filename}': {e}")
                content_buffer.close()
                return False
        content_buffer.write("\n")
        consolidated_md_body_content = content_buffer.getvalue()
        content_buffer.close()

    print_info("-> Генерация Markdown оглавления...")
    md_toc_content = generate_md_toc_from_text(consolidated_md_body_content, toc_max_depth)
    if md_toc_content is None:
        return False

    print_info(f"-> Запись итогового Markdown файла '{output_path_md}'...")
    try:
        os.makedirs(os.path.dirname(output_path_md), exist_ok=True)
        with open(output_path_md, 'w', encoding='utf-8') as outfile:
            outfile.write(toc_title + "\n\n")
            if md_toc_content:
                 outfile.write(md_toc_content + "\n\n")
            if consolidated_md_body_content:
                 outfile.write(consolidated_md_body_content)
        print_success(f"   Успешно сохранен: {output_path_md}")
        return True
    except Exception as e:
        print_error(f"Ошибка записи Markdown файла '{output_path_md}': {e}")
        return False

def convert_md_file_to_html(input_md_path, output_html_path):
    """Шаг 2: Читает MD файл (с уже готовым оглавлением),
       конвертирует его в HTML и сохраняет результат.
       Возвращает строку с полным HTML или None при ошибке.
    """
    print_info(f"-> Чтение итогового Markdown файла '{input_md_path}'...")
    try:
        with open(input_md_path, 'r', encoding='utf-8') as f:
            md_full_content = f.read()
    except FileNotFoundError:
         print_error(f"Входной Markdown файл '{input_md_path}' не найден.")
         return None
    except Exception as e:
         print_error(f"Ошибка чтения Markdown файла '{input_md_path}': {e}")
         return None

    print_info(f"-> Конвертация '{input_md_path}' в HTML...")
    try:
        # ВОЗВРАЩАЕМ 'toc' с той же конфигурацией slugify, чтобы он добавил правильные ID к заголовкам!
        md = markdown.Markdown(
            extensions=['toc', 'extra', 'codehilite'],
            extension_configs={
                # Конфигурация toc нужна для правильных ID, но сам блок ToC мы не используем
                'toc': { 
                    # 'toc_depth' здесь не так важен, т.к. сам блок toc не выводится
                    # 'title' тоже не важен
                    'slugify': slugify_unicode 
                },
                'codehilite': {'css_class': 'highlight'}
            }
        )
        # Конвертируем ВЕСЬ markdown контент (включая MD-оглавление) в HTML
        full_html_body_content = md.convert(md_full_content)
        # ПРИМЕЧАНИЕ: Мы НЕ используем md.toc здесь, т.к. оглавление уже преобразовано из MD.
    except Exception as e:
        print_error(f"Ошибка при конвертации Markdown в HTML: {e}")
        return None

    print_info(f"-> Формирование и сохранение HTML файла '{output_html_path}'...")
    html_template = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{OUTPUT_FILENAME_BASE}</title>  <!-- Используем базовое имя файла для заголовка -->
    <style>
        /* --- Встраивание шрифтов --- */
        @font-face {{
            font-family: 'DejaVuCustom';
            src: url('{os.path.join(FONTS_DIR, 'DejaVuSans.ttf')}');
            font-weight: normal;
            font-style: normal;
        }}
        @font-face {{
            font-family: 'DejaVuCustom';
            src: url('{os.path.join(FONTS_DIR, 'DejaVuSans-Bold.ttf')}');
            font-weight: bold;
            font-style: normal;
        }}
        @font-face {{
            font-family: 'DejaVuCustom';
            src: url('{os.path.join(FONTS_DIR, 'DejaVuSans-Oblique.ttf')}');
            font-weight: normal;
            font-style: italic;
        }}
         @font-face {{
            font-family: 'DejaVuCustom';
            src: url('{os.path.join(FONTS_DIR, 'DejaVuSans-BoldOblique.ttf')}');
            font-weight: bold;
            font-style: italic;
        }}
        @font-face {{
            font-family: 'DejaVuMonoCustom';
            src: url('{os.path.join(FONTS_DIR, 'DejaVuSansMono.ttf')}');
            font-weight: normal;
            font-style: normal;
        }}

        /* --- Основные стили с акцентом на PDF --- */
        body {{ font-family: 'DejaVuCustom', sans-serif; line-height: 1.4; padding: 20pt; max-width: 550pt; margin: auto; font-size: 10pt; /* Базовый размер шрифта (уменьшен) */ }}
        h1, h2, h3, h4, h5, h6 {{
            font-family: 'DejaVuCustom', sans-serif;
            font-weight: bold;
            margin-top: 12pt;
            margin-bottom: 6pt;
            padding: 0;
            border: none;
        }}
        h1 {{ font-size: 14pt; }} /* Уменьшено */
        h2 {{ font-size: 12pt; }} /* Уменьшено */
        h3 {{ font-size: 11pt; }} /* Уменьшено */
        p {{
            font-family: 'DejaVuCustom', sans-serif;
            margin: 0 0 5pt 0; /* Слегка уменьшен нижний отступ параграфа */
            padding: 0;
            text-align: justify;
        }}
        ul, ol {{
            margin: 0 0 6pt 0;
            padding-left: 20pt; /* Отступ слева для списка */
        }}
        li {{
            margin-bottom: 3pt; /* Небольшой отступ между элементами списка */
            padding: 0;
        }}
        strong, b {{ font-weight: bold; }}
        em, i {{ font-style: italic; }}
        code {{ font-family: 'DejaVuMonoCustom', monospace; background-color: #f0f0f0; padding: 1pt 3pt; border-radius: 3px; font-size: 0.9em; }}
        pre > code {{
             display: block;
             font-family: 'DejaVuMonoCustom', monospace;
             background-color: #f8f8f8;
             padding: 8pt;
             margin: 0 0 6pt 0;
             border-radius: 4px;
             overflow: hidden; /* Может помочь с рендерингом */
             white-space: pre-wrap; /* Перенос строк в коде */
             word-wrap: break-word; /* Перенос длинных слов */
        }}
        /* Стили подсветки кода */
        .highlight .hll {{ background-color: #ffffcc }}
        .highlight .c {{ color: #999988; font-style: italic }}
        /* ... */

        /* --- PDF-специфичные стили --- */
        @media print {{
            body {{
                font-size: 8pt; /* Еще уменьшено для PDF */
                padding: 10pt; /* Еще уменьшены поля для PDF */
                max-width: none; /* Снимаем ограничение ширины для PDF */
            }}
            h1 {{ font-size: 11pt; margin-top: 8pt; margin-bottom: 4pt; }} /* Еще уменьшено для PDF */
            h2 {{ font-size: 10pt; margin-top: 7pt; margin-bottom: 3pt; }} /* Еще уменьшено для PDF */
            h3 {{ font-size: 9pt; margin-top: 6pt; margin-bottom: 3pt;}} /* Еще уменьшено для PDF */
            p {{ margin-bottom: 3pt; }} /* Еще уменьшен отступ параграфа для PDF */
            ul, ol {{ margin-bottom: 4pt; padding-left: 15pt; }} /* Уменьшены отступы списков */
            li {{ margin-bottom: 1pt; }} /* Уменьшен отступ элемента списка */
            pre > code {{ padding: 5pt; margin-bottom: 4pt; font-size: 0.85em; }} /* Уменьшены отступы и шрифт кодовых блоков */
        }}
    </style>
</head>
<body>
<!-- Просто вставляем весь сконвертированный HTML -->
{full_html_body_content}
</body>
</html>"""
    try:
        os.makedirs(os.path.dirname(output_html_path), exist_ok=True)
        with open(output_html_path, 'w', encoding='utf-8') as outfile:
             outfile.write(html_template)
        print_success(f"   Успешно сохранен: {output_html_path}")
        return html_template # Возвращаем HTML для PDF
    except Exception as e:
        print_error(f"Ошибка записи HTML файла '{output_html_path}': {e}")
        return None

def convert_html_string_to_pdf(html_content_string, output_path_pdf):
    """Шаг 3: Принимает строку HTML и конвертирует ее в PDF файл (используя WeasyPrint)."""
    if not html_content_string:
        print_error("Нет HTML контента для конвертации в PDF.")
        return False
    print_info(f"-> Конвертация HTML в PDF файл '{output_path_pdf}' (WeasyPrint)...")
    try:
        # Настройка конфигурации шрифтов для WeasyPrint
        # font_config = FontConfiguration() # Можно оставить по умолчанию
        # Создаем объект HTML на основе строки, base_url нужен для поиска ресурсов (шрифтов)
        # Используем путь к корневой папке проекта как base_url
        base_url = os.path.dirname(os.path.abspath(__file__))
        html = HTML(string=html_content_string, base_url=base_url)
        # Записываем PDF
        html.write_pdf(output_path_pdf)
        print_success(f"   Успешно сохранен: {output_path_pdf}")
        return True
    except Exception as e:
        print_error(f"Ошибка при конвертации HTML в PDF с WeasyPrint '{output_path_pdf}': {e}")
        print_warning("Убедитесь, что системные зависимости WeasyPrint (pango, cairo, libffi) установлены.")
        return False

def convert_md_file_to_docx(input_md_path, output_path_docx):
    """Шаг 4: Читает MD файл и конвертирует его в DOCX файл (используя pypandoc)."""
    print_info(f"-> Проверка доступности pandoc...")
    
    try:
        pandoc_version = pypandoc.get_pandoc_version()
        print_info(f"   Найден pandoc версии {pandoc_version}")
    except OSError as e:
        print_error(f"Pandoc не найден: {e}")
        print_warning("Установите pandoc с https://pandoc.org/installing.html")
        print_warning("MacOS: brew install pandoc")
        print_warning("Linux (Debian/Ubuntu): sudo apt-get install pandoc")
        return False
    
    # Проверка существования файла
    if not os.path.exists(input_md_path):
        print_error(f"Файл {input_md_path} не найден.")
        return False
    
    # Проверка расширения файла
    if not input_md_path.lower().endswith(('.md', '.markdown')):
        print_error(f"Файл {input_md_path} не является Markdown файлом.")
        return False
    
    print_info(f"-> Конвертация MD в DOCX файл '{output_path_docx}' (pypandoc)...")
    try:
        # Создаем директорию, если не существует
        os.makedirs(os.path.dirname(output_path_docx), exist_ok=True)
        
        # Формируем список дополнительных аргументов, убирая None
        extra_args = ['--standalone']
        if os.path.exists('reference.docx'):
            extra_args.append('--reference-doc=reference.docx')
        
        # Конвертируем MD в DOCX
        pypandoc.convert_file(
            input_md_path,              # Входной файл
            'docx',                     # Выходной формат
            outputfile=output_path_docx, # Выходной файл
            extra_args=extra_args       # Дополнительные аргументы
        )
        
        print_success(f"   Успешно сохранен: {output_path_docx}")
        return True
    except Exception as e:
        print_error(f"Ошибка при конвертации MD в DOCX с pypandoc '{output_path_docx}': {e}")
        return False

def single_file_to_docx(input_md_path):
    """Конвертирует отдельный MD файл в DOCX (для использования через аргумент командной строки)"""
    if not input_md_path:
        print_error("Не указан путь к MD файлу")
        return False
    
    # Определяем имя выходного файла
    output_path_docx = os.path.splitext(input_md_path)[0] + '.docx'
    
    print_header(f"--- Конвертация Markdown в DOCX ---")
    print_info(f"Входной файл: {input_md_path}")
    print_info(f"Выходной файл: {output_path_docx}")
    
    # Вызываем общую функцию конвертации
    docx_success = convert_md_file_to_docx(input_md_path, output_path_docx)
    
    if docx_success:
        print_header(f"\nDOCX успешно создан: {output_path_docx}")
        return True
    else:
        print_error(f"\nНе удалось конвертировать {input_md_path} в DOCX")
        return False

def convert_pdf_to_md(input_pdf_path, output_md_path=None, split_by_pages=False):
    """Конвертирует PDF файл в Markdown формат.
    
    Аргументы:
        input_pdf_path (str): Путь к входному PDF файлу
        output_md_path (str, optional): Путь для сохранения Markdown файла. Если None, сохраняется рядом с PDF
        split_by_pages (bool, optional): Разделять ли текст на страницы с разделителями. По умолчанию False
    
    Возвращает:
        bool: True в случае успеха, False при ошибке
    """
    print_info(f"-> Проверка файла PDF: '{input_pdf_path}'...")
    
    # Проверка существования файла
    if not os.path.exists(input_pdf_path):
        print_error(f"Файл {input_pdf_path} не найден.")
        return False
    
    # Проверка расширения файла
    if not input_pdf_path.lower().endswith('.pdf'):
        print_error(f"Файл {input_pdf_path} не является PDF файлом.")
        return False
    
    # Если output_md_path не указан, создаем имя из input_pdf_path
    if not output_md_path:
        output_md_path = os.path.splitext(input_pdf_path)[0] + '.md'
    
    print_info(f"-> Извлечение текста из PDF '{input_pdf_path}'...")
    try:
        # Создаем директорию, если не существует
        os.makedirs(os.path.dirname(output_md_path), exist_ok=True)
        
        # Открываем PDF файл
        reader = PdfReader(input_pdf_path)
        
        # Получаем количество страниц
        num_pages = len(reader.pages)
        print_info(f"   Найдено {num_pages} страниц")
        
        # Открываем файл для записи Markdown
        with open(output_md_path, 'w', encoding='utf-8') as md_file:
            # Добавляем заголовок с информацией о файле
            title = os.path.basename(input_pdf_path)

            # Извлекаем текст из каждой страницы
            for i, page in enumerate(reader.pages):
                print_info(f"   Обработка страницы {i+1}/{num_pages}...")
                
                # Извлекаем текст
                text = page.extract_text()
                
                # Если включено разделение по страницам и это не первая страница, добавляем разделитель
                if split_by_pages and i > 0:
                    md_file.write("\n---\n\n")
                
                # Добавляем номер страницы только если включено разделение по страницам
                if split_by_pages:
                    md_file.write(f"**Страница {i+1}**\n\n")
                
                # Пишем текст, разбивая на параграфы
                paragraphs = text.split('\n')
                for para in paragraphs:
                    # Убираем лишние переносы строк внутри параграфа
                    clean_para = para.replace('\n', ' ').strip()
                    if clean_para:
                        md_file.write(f"{clean_para}\n\n")
        
        print_success(f"   Успешно сохранен: {output_md_path}")
        return True
    except Exception as e:
        print_error(f"Ошибка при конвертации PDF в Markdown: {e}")
        return False

def single_pdf_to_md(input_pdf_path, split_by_pages=False):
    """Конвертирует отдельный PDF файл в MD (для использования через аргумент командной строки)"""
    if not input_pdf_path:
        print_error("Не указан путь к PDF файлу")
        return False
    
    # Определяем имя выходного файла
    output_path_md = os.path.splitext(input_pdf_path)[0] + '.md'
    
    print_header(f"--- Конвертация PDF в Markdown ---")
    print_info(f"Входной файл: {input_pdf_path}")
    print_info(f"Выходной файл: {output_path_md}")
    print_info(f"Разделение на страницы: {'Да' if split_by_pages else 'Нет'}")
    
    # Вызываем функцию конвертации
    md_success = convert_pdf_to_md(input_pdf_path, output_path_md, split_by_pages)
    
    if md_success:
        print_header(f"\nMarkdown успешно создан: {output_path_md}")
        return True
    else:
        print_error(f"\nНе удалось конвертировать {input_pdf_path} в Markdown")
        return False

# === Основной блок ===

if __name__ == "__main__":
    # Парсим аргументы командной строки
    parser = argparse.ArgumentParser(description='Сборка документации и конвертация форматов')
    parser.add_argument('--convert2docx', dest='convert2docx', help='Путь к MD файлу для конвертации в DOCX')
    parser.add_argument('--convert2md', dest='convert2md', help='Путь к PDF файлу для конвертации в Markdown')
    parser.add_argument('--split-pages', action='store_true', help='Разделять PDF на страницы при конвертации в Markdown')
    args = parser.parse_args()
    
    # Если указан аргумент --convert2md, конвертируем PDF в Markdown
    if args.convert2md:
        split_by_pages = args.split_pages
        success = single_pdf_to_md(args.convert2md, split_by_pages)
        sys.exit(0 if success else 1)
    
    # Если указан аргумент --convert2docx, конвертируем только этот файл в DOCX
    if args.convert2docx:
        success = single_file_to_docx(args.convert2docx)
        sys.exit(0 if success else 1)
    
    # Иначе выполняем полную сборку всех форматов
    print_header("--- Начало сборки документов ---")
    output_path_md = os.path.join(GENERATED_DIR, OUTPUT_MD)
    output_path_html = os.path.join(GENERATED_DIR, OUTPUT_HTML)
    output_path_pdf = os.path.join(GENERATED_DIR, OUTPUT_PDF)
    output_path_docx = os.path.join(GENERATED_DIR, OUTPUT_DOCX) # Путь к DOCX

    # Шаг 1: Создаем MD файл
    print_subheader("\n=== Шаг 1: Создание Markdown ===")
    md_success = create_consolidated_md(
        source_dir=SOURCE_DIR,
        output_path_md=output_path_md,
        toc_title=TOC_TITLE_MD,
        toc_max_depth=TOC_MAX_DEPTH
    )

    if not md_success:
        print_error("\nСборка прервана: Ошибка на шаге создания MD файла")
        sys.exit(1)

    # Шаг 2: Создаем HTML из СОХРАНЕННОГО MD файла
    print_subheader("\n=== Шаг 2: Создание HTML ===")
    html_content_for_pdf = convert_md_file_to_html(
        input_md_path=output_path_md,
        output_html_path=output_path_html
    )

    if html_content_for_pdf is None:
        print_error("\nСборка прервана: Ошибка на шаге создания HTML файла")
        sys.exit(1)

    # Шаг 3: Создаем PDF из HTML
    print_subheader("\n=== Шаг 3: Создание PDF ===")
    pdf_success = convert_html_string_to_pdf(
        html_content_string=html_content_for_pdf,
        output_path_pdf=output_path_pdf
    )

    # Не прерываем сборку, если PDF не удался, но сообщаем
    if not pdf_success:
        print_warning("\nНе удалось создать PDF файл\n")
        # sys.exit(1) # Не выходим, продолжаем с DOCX

    # Шаг 4: Создаем DOCX из MD
    print_subheader("\n=== Шаг 4: Создание DOCX ===")
    docx_success = convert_md_file_to_docx(
        input_md_path=output_path_md,
        output_path_docx=output_path_docx
    )

    if not docx_success:
        print_warning("\nНе удалось создать DOCX файл\n")
        # Не выходим, даже если и PDF, и DOCX не удались, т.к. MD и HTML могли быть созданы

    print_header("\n--- Сборка завершена --- ")
    if pdf_success and docx_success:
        print_success("(MD, HTML, PDF, DOCX созданы)")
    elif pdf_success:
        print_success("(MD, HTML, PDF созданы)")
        print_warning("(DOCX - ошибка)")
    elif docx_success:
        print_success("(MD, HTML, DOCX созданы)")
        print_warning("(PDF - ошибка)")
    else:
        print_success("(MD, HTML созданы)")
        print_warning("(PDF и DOCX - ошибка)")

    sys.exit(0)
