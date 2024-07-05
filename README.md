# DAISY PARSER

Инициализация парсера:  
```
parser = DaisyParser(folder_path)
```
folder_path - абсолютный путь к папке с книгой.  
Версия DAISY определяется автоматически (2.02 или 3.0)

## Публичные методы:  

### 1. Получить имя автора и название книги
```
get_creator_and_title() -> dict
```
Возвращает словарь вида
```
{'creator': 'creator', 'title': 'title'}
```
либо пустой словарь, если не удалось определить версию или найти метаданные
### 2. Получить словарь аудио в правильном порядке
```
get_audios_dict() -> dict[str, int]
```
Возвращает словарь вида
```
{'bagw0019.mp3': 30000, 'bagw001A.mp3': 22000, 'bagw001B.mp3': 48000, 'bagw0014.mp3': 65000, 'bagw0018.mp3': 11000, 'bagw001C.mp3': 75000, 'bagw0017.mp3': 21000, 'bagw001D.mp3': 56000}
```
где ключ - название аудио, значение - время фрагмента в мс
### 3. Установить опцию навигации (страница, заголовок, фраза, группа)  
```
set_nav_option(nav_option: NavOption) -> None
```
```
class NavOption(IntEnum):
    PHRASE = 0
    HEADING = 1
    PAGE = 2
    GROUP = 3
```
Устанавливает опцию навигации
### 4. Получить следующий объект навигации
```
get_next(current_audio_path: str, current_time: float) -> Optional[NavItem]
```
```
class NavItem:
    audio_path: str
    start_time: float
    end_time: float
    text: str
```
Принимает параметры:

- current_audio_path: str - путь к текущему проигрываемому MP3-файлу (относительно папки)
- current_time: float - текущее время от начала проигрывания данного MP3-файла

Возвращает:

- объект навигации в виде
```
{'audio_path': 'bagw0014.mp3', 'start_time': 63.957, 'end_time': 65.304, 'text': '5'}
```
- None, если current_audio_path последний в списке, а current_time - последняя фраза в current_audio_path  

Параметры ответа:
- text: str - опциональный (только для Heading, Page и Group, для Phrase - пустая строка)
- audio_path: str - путь к MP3-файлу, в котором находится следующий объект навигации
- start_time: str - время начала следующего объекта навигации в audio_path
- end_time: str - время конца следующего объекта навигации в audio_path
### 5. Получить предыдущий объект навигации
```
get_prev(current_audio_path: str, current_time: float) -> Optional[NavItem]
```
```
class NavItem:
    audio_path: str
    start_time: float
    end_time: float
    text: str
```
Принимает параметры:
- current_audio_path: str - путь к текущему проигрываемому MP3-файлу (относительно папки)
- current_time: float - текущее время от начала проигрывания данного MP3-файла

Возвращает:

- объект навигации в виде
```
{'audio_path': 'bagw0014.mp3', 'start_time': 63.957, 'end_time': 65.304, 'text': '5'}
```
- None, если current_audio_path первый в списке, а current_time - первая фраза в current_audio_path

Параметры ответа:
- text: str - опциональный (только для Heading, Page и Group, для Phrase - пустая строка)
- audio_path: str - путь к MP3-файлу, в котором находится предыдущий объект навигации
- start_time: str - время начала предыдущего объекта навигации в audio_path
- end_time: str - время конца предыдущего объекта навигации в audio_path
### 6. Получить общее время книги
get_total_time() -> Optional[float]  
Возвращает общее время книги в секундах или None, если тег времени не найден
