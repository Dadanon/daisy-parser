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
либо пустой словарь, если не удалось определить версию  
или найти метаданные
### 2. Получить список аудио в правильном порядке
```
get_audios_list() -> list[str]
```
Возвращает словарь вида
```
['audio_1.mp3', 'audio_2.mp3', 'audio_3.mp3']
```
### 3. Установить опцию навигации (страница, заголовок, фраза)  
```
set_nav_option(nav_option: NavOption) -> None
```
```
class NavOption(IntEnum):
    PHRASE = 0
    HEADING = 1
    PAGE = 2
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
или None, если current_audio_path последний в списке, а current_time - последняя фраза в current_audio_path  

Параметры
- text: str - опциональный (только для Heading и Page, для Phrase - пустая строка)
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
или None, если current_audio_path первый в списке, а current_time - первая фраза в current_audio_path

Параметры
- text: str - опциональный (только для Heading и Page, для Phrase - пустая строка)
- audio_path: str - путь к MP3-файлу, в котором находится предыдущий объект навигации
- start_time: str - время начала предыдущего объекта навигации в audio_path
- end_time: str - время конца предыдущего объекта навигации в audio_path
