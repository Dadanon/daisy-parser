import time
from enum import IntEnum
from typing import Optional, List, Tuple, Dict
import re
from collections import OrderedDict

from bs4 import BeautifulSoup, PageElement


class NavOption(IntEnum):
    PHRASE = 0
    HEADING = 1
    PAGE = 2


class NavigationItem:
    number: int  # Порядковый номер
    name: Optional[str]  # Название для проговаривания при навигации, отсутствует для фраз
    fragment_name: str  # Имя конкретного mp3-файла, в котором находится этот экземпляр
    time_start: float  # Время от начала относительно текущего mp3-файла
    elapsed_time: float  # Время от начала относительно начала книги
    fragment_duration: float  # Длительность текущего mp3-файла

    def __init__(self, number: int, name: Optional[str] = None, fragment_name: str = '', time_start: float = -1, elapsed_time: float = -1, duration: float = -1):
        self.number = number
        self.name = name
        self.fragment_name = fragment_name
        self.time_start = time_start
        self.elapsed_time = elapsed_time
        self.fragment_duration = duration


class Smil:
    name: str  # Название
    path: str  # Путь к файлу smil
    soup: Optional[BeautifulSoup]  # Контент файла после парсинга, задается после инициализации

    def __init__(self, name: str, path: str):
        self.name = name
        self.path = path
        self.soup = None

    def __str__(self):
        return f"Name: {self.name}, path: {self.path}"


patterns = {
    'get_audio_src': r'<audio[^>]*\ssrc="([^"]+)"',  # Получаем значение атрибута src в теге audio
    'get_smil_name': r'href="([^"]+\.smil)#',  # Получаем название smil из ncc.html в виде s0002.smil
    'get_audio_info': r'<audio[^>]*src="([^"]+)"[^>]*clip-begin="npt=([0-9]+(?:\.[0-9]*)?)s"[^>]*clip-end="npt=([0-9]+(?:\.[0-9]*)?)s"[^>]*>'  # Получаем временной интервал
}


class DaisyParser:
    """
    Будем считать, что отдельный smil относится к
    отдельному MP3-фрагменту. Такая логика даже в
    600Мб файле на 835 страниц.
    """
    folder_path: str
    _nav_option: NavOption
    _audios_smils: Dict[str, Tuple[int, str]]  # Словарь, где ключ - путь к аудиофайлу, а значение - массив с позицией данного файла и соответствующим именем smil
    _positions_audios: Dict[int, str]  # Словарь где мы храним порядковый номер каждого аудио как ключ и путь к аудио - как значение

    def __init__(self, folder_path: str):
        """
        Инициализируем экземпляр парсера
        для конкретной папки с книгой. Также
        мы сразу парсим ncc.html, это
        достаточно быстро
        (для ~600Мб файла с html.parser - ~ 11-12с)
        """
        start_time = time.time()
        self.folder_path = folder_path
        self._nav_option = NavOption.PHRASE
        self._audios_smils = {}
        """Словарь, ключ - путь к mp3, значение - (порядковый номер аудио, имя smil)"""
        self._positions_audios = {}
        """Словарь, ключ - порядковый номер аудио, значение - путь к mp3"""
        self._prepare_dicts()
        # print(self._audios_smils)
        # print('\n\n\n')
        # print(self._positions_audios)
        # print('\n\n\n')
        end_time = time.time()
        print(f'\nTotal parse time: {end_time - start_time:0.4f} seconds\n')

    def _prepare_dicts(self):
        """
        1) Получаем словарь позиция - путь аудио
        2) Получаем словарь путь аудио - (путь smil, позиция)
        """
        ncc_content = self.try_open(f'{self.folder_path}/ncc.html')
        smil_names = list(OrderedDict.fromkeys(re.findall(patterns['get_smil_name'], ncc_content)))
        # print(smil_names)
        current_smil_position: int = 1
        for name in smil_names:
            if corresponding_audio_name := self.find_audio_name(f"{self.folder_path}/{name}"):
                self._positions_audios[current_smil_position] = corresponding_audio_name
                self._audios_smils[corresponding_audio_name] = current_smil_position, name
                current_smil_position += 1

    @staticmethod
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

    def set_nav_option(self, nav_option: NavOption):
        """
        Метод API, мы выбираем соответствующую опцию для
        навигации, передавая в сигнатуру выбранную опцию
        """
        self._nav_option = nav_option

    def get_next(self, current_audio_path: str, current_time: float):
        """
        Метод API, при нажатии кнопки вправо мы вызываем этот
        метод, передавая в сигнатуру текущий путь проигрываемого
        MP3-фрагмента и время от начала проигрывания
        """
        return self.get_next_phrase(current_audio_path, current_time)

    def get_next_phrase(self, current_audio_path: str, current_time: float) -> Optional[Tuple[str, float, float]]:
        """Ищет audio тэг, в интервал которого попадает current_time.\n
        1. Для следующего audio тега возвращает имя mp3, время начала и время конца.\n
        2. Если следующий audio тег не найден - ищет в следующем по порядку smil файле.\n
        3. Если первоначальный smil был последним - возвращает None"""
        position, smil_name = self._audios_smils.get(current_audio_path)
        if not position or not smil_name:
            raise ValueError(f"Данному mp3-файлу {current_audio_path} не присвоен соответствующий smil")
        smil_content = self.try_open(f"{self.folder_path}/{smil_name}")
        matches = re.finditer(patterns['get_audio_info'], smil_content)
        for match in matches:
            clip_begin = float(match.group(2))
            clip_end = float(match.group(3))
            if clip_begin <= current_time < clip_end:
                try:
                    next_match = next(matches)
                    return next_match.group(1), float(next_match.group(2)), float(next_match.group(3))  # 1 вариант
                except StopIteration:
                    next_audio_path: str = self._positions_audios.get(position + 1)
                    if next_audio_path:
                        next_position, next_smil_name = self._audios_smils.get(next_audio_path)
                        if not next_position or not next_smil_name:
                            raise ValueError(f"Данному mp3-файлу {next_audio_path} не присвоен соответствующий smil")
                        next_smil_content = self.try_open(f"{self.folder_path}/{next_smil_name}")
                        next_audio_info = re.search(patterns['get_audio_info'], next_smil_content)
                        if next_audio_info:
                            return next_audio_info.group(1), float(next_audio_info.group(2)), float(next_audio_info.group(3))  # 2 вариант

    def _get_prev_phrase(self, current_audio_path: str, current_time: float) -> Optional[Tuple[Optional[str], float]]:
        """
        Получаем предыдущую фразу, учитывая текущий проигрываемый
        фрагмент и время воспроизведения

        :return:
        """
        ...

    @staticmethod
    def try_open(file_path) -> str:
        encodings = ['utf-8', 'ansi', 'cp1251', 'latin-1']
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as file:
                    return file.read()
            except (UnicodeDecodeError, LookupError):
                continue
        raise Exception(f"Кодировка файла {file_path} не найдена в списке {encodings}")


parser = DaisyParser("frontpage")
start_time = time.time()
file_to_use, time_start, time_end = parser.get_next("823_r.mp3", 456.5)
print(f"File: {file_to_use}, start time: {time_start}, end time: {time_end}")
file_to_use_next, new_time_start, new_time_end = parser.get_next(file_to_use, time_start)
print(f"New file: {file_to_use_next}, new start time: {new_time_start}, new end time: {new_time_end}")
file_to_use_3, time_start_3, time_end_3 = parser.get_next(file_to_use_next, new_time_start)
print(f"New file: {file_to_use_3}, new start time: {time_start_3}, new end time: {time_end_3}")
end_time = time.time()
print(f"Время между 3 запросами: {end_time - start_time}")
