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
    'get_audio_interval': r'<audio[^>]*src="[^"]+"[^>]*clip-begin="npt=([0-9]+(?:\.[0-9]*)?)s"[^>]*clip-end="npt=([0-9]+(?:\.[0-9]*)?)s"[^>]*>'  # Получаем временной интервал
}


class DaisyParser:
    """
    Будем считать, что отдельный smil относится к
    отдельному MP3-фрагменту. Такая логика даже в
    600Мб файле на 835 страниц.
    """
    folder_path: str
    _nav_option: NavOption
    _smils: List[Smil]
    _ncc_soup: BeautifulSoup
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
        self._smils = []
        # self._set_ncc_soup()
        self._audios_smils = {}
        self._positions_audios = {}
        self._prepare_dicts()
        print(self._audios_smils)
        print('\n\n\n')
        print(self._positions_audios)
        print('\n\n\n')
        end_time = time.time()
        print(f'\nTotal parse time: {end_time - start_time:0.4f} seconds\n')

    def _prepare_dicts(self):
        """
        1) Получаем словарь позиция - путь аудио
        2) Получаем словарь путь аудио - (путь smil, позиция)
        """
        ncc_content = self.try_open(f'{self.folder_path}/ncc.html')
        smil_names = list(OrderedDict.fromkeys(re.findall(patterns['get_smil_name'], ncc_content)))
        print(smil_names)
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
        return self._get_next_phrase(current_audio_path, current_time)

    def _get_next_phrase(self, current_audio_path: str, current_time: float) -> Optional[Tuple[Optional[str], float, float]]:
        """
        Получаем следующую фразу, учитывая текущий проигрываемый
        фрагмент, время начала проигрывания фразы и время конца проигрывания фразы
        1. Найти smil, соответствующий проигрываемому фрагменту
        2. Найти аудио с интервалом, в который попадает current_time
        3.1. Если этот аудио НЕ последний в текущем фрагменте -
        найти следующий аудио, записать clip-begin
        3.2. Если аудио последний - вернуть название следующего фрагмента и 0 как время начала
        :return название фрагмента (опционально - только если следующая
        фраза уже в другом файле) и время начала следующей фразы
        """
        position, smil = self._audios_smils.get(current_audio_path)
        if position and smil:
            if not smil.soup:
                smil_content = self.try_open(smil.path)
                if not smil_content:
                    return None
                smil.soup = BeautifulSoup(smil_content, 'html.parser')
            result = self._find_next_phrase_interval(smil.soup, current_time)
            match result:
                case None:
                    if next_audio_path := self._positions_audios.get(position + 1):
                        _, next_smil = self._audios_smils.get(next_audio_path)
                        if next_smil:
                            if not next_smil.soup:
                                next_smil_content = self.try_open(next_smil.path)
                                if not next_smil_content:
                                    return None
                                next_smil.soup = BeautifulSoup(next_smil_content, 'html.parser')
                        next_audio_tag = next_smil.soup.find('audio')
                        next_start_time, next_end_time = self._get_chunk_interval(next_audio_tag)
                        return next_audio_path, next_start_time, next_end_time
                case start_time, end_time:
                    return current_audio_path, start_time, end_time

    def _get_prev_phrase(self, current_audio_path: str, current_time: float) -> Optional[Tuple[Optional[str], float]]:
        """
        Получаем предыдущую фразу, учитывая текущий проигрываемый
        фрагмент и время воспроизведения

        :return:
        """
        ...

    @staticmethod
    def _get_chunk_interval(audio_chunk) -> Tuple[float, float]:
        """Возвращает начало и конец принятого аудио кусочка"""
        clip_begin = audio_chunk.get('clip-begin', '').replace('npt=', '').replace('s', '')
        clip_end = audio_chunk.get('clip-end', '').replace('npt=', '').replace('s', '')

        # Проверяем, присутствуют ли необходимые атрибуты
        if not clip_begin or not clip_end:
            raise AttributeError(f"У данного аудио кусочка: {audio_chunk} нет атрибутов clip-begin или clip-end")

        # Преобразуем в float для сравнения
        try:
            clip_begin = float(clip_begin)
            clip_end = float(clip_end)
        except ValueError:
            raise ValueError(f"Атрибуты clip-begin: {clip_begin} или clip-end: {clip_end} не являются числами")

        return clip_begin, clip_end

    @staticmethod
    def _find_next_phrase_interval(smil_soup: BeautifulSoup, current_time: float) -> Optional[Tuple[float, float]]:
        """
        Возвращает:\n
        - начало и конец следующего кусочка mp3, если в интервал предыдущего попадает current_time
        - None, если данный кусочек последний в данном smil - значит, надо искать в следующем или кусочек не найден
        """
        audio_tags = smil_soup.find_all('audio')

        for i in range(len(audio_tags)):
            clip_begin, clip_end = DaisyParser._get_chunk_interval(audio_tags[i])

            # Проверяем, попадает ли current_time в интервал [clip_begin, clip_end]
            if clip_begin <= current_time < clip_end:
                next_tag = audio_tags[i + 1] if i + 1 < len(audio_tags) else None
                if next_tag:
                    return DaisyParser._get_chunk_interval(audio_tags[i + 1])
        return None

    @staticmethod
    def _time_to_seconds(time_str: str) -> float:
        ms_index = time_str.find('.')
        if ms_index == -1:
            time_str = time_str + '.000'
        try:
            h, m, s, ms = map(float, re.split('[:.]', time_str))
            return h * 3600 + m * 60 + s + ms / 1000
        except ValueError as e:
            print(f'Bad time string: {time_str}, error: {e}')

    @staticmethod
    def try_open(file_path) -> Optional[str]:
        encodings = ['utf-8', 'ansi', 'cp1251', 'latin-1']
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as file:
                    return file.read()
            except (UnicodeDecodeError, LookupError):
                continue
        return None


parser = DaisyParser("frontpage")
# start_time = time.time()
# file_to_use, time_start, time_end = parser.get_next("823_r.mp3", 46.3)
# print(f"File: {file_to_use}, start time: {time_start}, end time: {time_end}")
# file_to_use_next, new_time_start, new_time_end = parser.get_next(file_to_use, time_start)
# print(f"New file: {file_to_use_next}, new start time: {new_time_start}, new end time: {new_time_end}")
# file_to_use_3, time_start_3, time_end_3 = parser.get_next(file_to_use_next, new_time_start)
# print(f"New file: {file_to_use_3}, new start time: {time_start_3}, new end time: {time_end_3}")
# end_time = time.time()
# print(f"Время между 3 запросами: {end_time - start_time}")
