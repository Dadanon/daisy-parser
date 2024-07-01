import itertools
import re
from enum import IntEnum
from typing import Optional, Union, Literal

patterns = {
    'get_audio_src': r'<audio[^>]*\ssrc="([^"]+)"',  # Получаем значение атрибута src в теге audio
    'get_smil_name': r'href="([^"]+\.smil)#',  # Получаем название smil из ncc.html в виде s0002.smil
    'get_audio_info': r'<audio[^>]*src="([^"]+)"[^>]*clip-begin="npt=([0-9]+(?:\.[0-9]*)?)s"[^>]*clip-end="npt=([0-9]+(?:\.[0-9]*)?)s"[^>]*>',
    # Получаем временной интервал'
    'get_all_pages': r'<span class="[^"]*" id="[^"]*"><a href="([^"]*)">([^<]*)</a></span>',
    # Получаем список всех страниц
    'get_headings': r'<h[1-6][^>].*?><a href="([^"#].*?)#([^"].*?)">([^<].*?)</a></h[1-6]>',
    # Получаем список заголовков в формате [('icth0001.smil', 'icth0001', 'A light Man'), ('icth0002.smil', 'icth_0001', 'Epigraph')...]
    'get_pages': r'<span[^>].*?><a href="([^"#].*?)#([^"].*?)">([^<].*?)</a></span>',
    # INFO: шаблоны для 3 версии
    'get_spine_content': r'<spine>(.*?)</spine>',  # Получаем содержимое блока spine
    'get_spine_ordered_items': r'idref="(.*?)"',  # Получаем список id smil по порядку в виде ['smil-1', smil-2'...]
    'get_manifest_content': r'<manifest>(.*?)</manifest>',  # Получаем блок, в котором получим названия smil
    'get_page_list_block': r'<pageList[^>]+>(.*?)</pageList>',  # Получаем блок pageList со списком страниц
    'get_pages_list': r'<pageTarget[^>]*>[^<].*?<navLabel>[^<].*?<text>([^<].*?)</text>[^<].*?<audio([^/].*?)/>([^<].*?)</navLabel>([^<].*?)',
    # Получаем список страниц в виде [('1', 'clipBegin="0:00:34.218" clipEnd="0:00:35.388" src="speechgen0002.mp3"'), ('2', 'clipBegin="0:00:43.751" clipEnd="0:00:46.958" src="speechgen0003.mp3"')...], параметры: текст, время начала, время конца, название mp3
    'get_clip_begin': r'clipBegin="(.*?)"',
    'get_clip_end': r'clipEnd="(.*?)"',
    'get_src': r'src="(.*?)"',
    'get_nav_map_block': r'<navMap.*?>(.*?)</navMap>',
    'get_nav_points': r'<navPoint class="h[1-6][^>].*?>[^<].*?<navLabel>[^<].*?<text>([^<].*?)</text>[^<].*?<audio([^<].*?)/>',
    # Получить информацию по страницам
    'get_smil_audio_list': r'<audio([^/].*?)/>'
}


DIRECTION = Union[Literal[1], Literal[-1]]


class NavItem:
    """Получаем путь к аудио, время начала, время конца, текст заголовка или страницы"""
    audio_path: str
    start_time: float
    end_time: float
    text: str

    def __init__(self, audio_path: str, start_time: float, end_time: float, text: str = ''):
        self.audio_path = audio_path
        self.start_time = start_time
        self.end_time = end_time
        self.text = text


class NavOption(IntEnum):
    PHRASE = 0
    HEADING = 1
    PAGE = 2


DAISY_VERSIONS = ['2.0', '2.02', '3.0']


def time_str_to_seconds(time_str: str) -> float:
    ms_index = time_str.find('.')
    if ms_index == -1:
        time_str = time_str + '.000'
    try:
        h, m, s, ms = map(float, re.split('[:.]', time_str))
        return h * 3600 + m * 60 + s + ms / 1000
    except ValueError as e:
        print(f'Bad time string: {time_str}, error: {e}')


def get_id_position_in_text(id_str: str, file_content: str, file_name: str = '') -> int:
    pattern = rf'{id_str}'
    match = re.search(pattern, file_content)
    if not match:
        raise ValueError(f'Отсутствует элемент с id = {id_str} в {file_name}')
    return match.start()


def find_audio_name(smil_path) -> Optional[str]:
    """
    Находит и возвращает название audio,
    соответствующего данному smil_path
    """
    encodings = ['utf-8', 'cp1251', 'latin-1', 'ansi']
    for encoding in encodings:
        try:
            with open(smil_path, 'r', encoding=encoding) as file:
                for line in file:
                    match = re.search(patterns['get_audio_src'], line)
                    if match:
                        return match.group(1)
        except (UnicodeDecodeError, LookupError):
            continue
    return None


def _pairwise(iterable):
    """Выдает пару элементов из итератора, чтобы иметь возможность осуществлять поиск в предыдущем значении"""
    a, b = itertools.tee(iterable)
    next(b, None)
    return zip(a, b)


def _pairwise_list(lst):
    return [(lst[i], lst[i + 1]) for i in range(len(lst) - 1)]


def try_open(file_path) -> str:
    encodings = ['utf-8', 'ansi', 'cp1251', 'latin-1']
    for encoding in encodings:
        try:
            with open(file_path, 'r', encoding=encoding) as file:
                return file.read()
        except (UnicodeDecodeError, LookupError):
            continue
    raise Exception(f"Кодировка файла {file_path} не найдена в списке {encodings}")
