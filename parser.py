import itertools
import time
from enum import IntEnum
from typing import Optional, List, Tuple, Dict, Iterator, Union
import re
from collections import OrderedDict


class NavOption(IntEnum):
    PHRASE = 0
    HEADING = 1
    PAGE = 2


class NavPhrase:
    """Получаем фразу для навигации, в которой
    храним путь к аудио, время начала и время конца"""
    audio_path: str
    start_time: float
    end_time: float

    def __init__(self, audio_path: str, start_time: float, end_time: float):
        self.audio_path = audio_path
        self.start_time = start_time
        self.end_time = end_time


class NavText:
    """Получаем текст заголовка или страницы и следующую
    фразу, с которой начнем озвучивание после нажатия ОК"""
    text: str
    next_phrase: NavPhrase

    def __init__(self, text: str, next_phrase: NavPhrase):
        self.text = text
        self.next_phrase = next_phrase


NavItem = Optional[Union[NavPhrase, NavText]]

patterns = {
    'get_audio_src': r'<audio[^>]*\ssrc="([^"]+)"',  # Получаем значение атрибута src в теге audio
    'get_smil_name': r'href="([^"]+\.smil)#',  # Получаем название smil из ncc.html в виде s0002.smil
    'get_audio_info': r'<audio[^>]*src="([^"]+)"[^>]*clip-begin="npt=([0-9]+(?:\.[0-9]*)?)s"[^>]*clip-end="npt=([0-9]+(?:\.[0-9]*)?)s"[^>]*>',
    # Получаем временной интервал'
}


class DaisyParser:
    """
    Будем считать, что отдельный smil относится к
    отдельному MP3-фрагменту. Такая логика даже в
    600Мб файле на 835 страниц.
    """
    folder_path: str
    _nav_option: NavOption
    _audios_smils: Dict[str, Tuple[
        int, str]]  # Словарь, где ключ - путь к аудиофайлу, а значение - массив с позицией данного файла и соответствующим именем smil
    _positions_audios: Dict[
        int, str]  # Словарь где мы храним порядковый номер каждого аудио как ключ и путь к аудио - как значение
    _ncc_content: str

    def __init__(self, folder_path: str):
        start_time = time.time()
        self.folder_path = folder_path
        self._nav_option = NavOption.PHRASE
        self._audios_smils = {}
        """Словарь, ключ - путь к mp3, значение - (порядковый номер аудио, имя smil)"""
        self._positions_audios = {}
        """Словарь, ключ - порядковый номер аудио, значение - путь к mp3"""
        self._ncc_content = self.try_open(f"{self.folder_path}/ncc.html")
        self._prepare_dicts()
        end_time = time.time()
        print(f'\nTotal parse time: {end_time - start_time:0.4f} seconds\n')

    def find_headings_by_prefix(self, smil_name: str) -> Iterator[re.Match[str]]:
        """Получить итератор заголовков, встречающихся в файле smil со smil_name"""
        pattern = rf'<h[1-6] id="[^"]*"><a href="({smil_name}[^"]*)">([^<]*)</a></h[1-6]>'
        matches = re.finditer(pattern, self._ncc_content)
        return matches

    def find_next_heading_from_position(self, position: int) -> Optional[re.Match[str]]:
        pattern = r'<h[1-6] id="[^"]*"><a href="([^"]*)">([^<]*)</a></h[1-6]>'
        next_match = re.search(pattern, self._ncc_content[position + 1:])
        return next_match

    @staticmethod
    def get_id_position_in_text(id_str: str, file_content: str) -> int:
        pattern = rf'{id_str}'
        match = re.search(pattern, file_content)
        return match.start()

    def get_smil_path(self, smil_name: str):
        return f"{self.folder_path}/{smil_name}"

    def _prepare_dicts(self):
        """
        1) Получаем словарь позиция - путь аудио
        2) Получаем словарь путь аудио - (путь smil, позиция)
        """
        smil_names = list(OrderedDict.fromkeys(re.findall(patterns['get_smil_name'], self._ncc_content)))
        current_smil_position: int = 1
        for name in smil_names:
            if corresponding_audio_name := self.find_audio_name(self.get_smil_path(name)):
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

    def _get_smil_content_position_name(self, audio_path: str) -> Tuple[str, int, str]:
        position, smil_name = self._audios_smils.get(audio_path)
        if not position or not smil_name:
            raise ValueError(f"Данному mp3-файлу {audio_path} не присвоен соответствующий smil")
        return self.try_open(self.get_smil_path(smil_name)), position, smil_name

    def get_next(self, current_audio_path: str, current_time: float) -> NavItem:
        """
        Метод API, при нажатии кнопки вправо мы вызываем этот
        метод, передавая в сигнатуру текущий путь проигрываемого
        MP3-фрагмента и время от начала проигрывания
        """
        match self._nav_option:
            case NavOption.PHRASE:
                return self._get_next_phrase(current_audio_path, current_time)
            case NavOption.HEADING:
                return self._get_next_heading(current_audio_path, current_time)
            case NavOption.PAGE:
                ...

    def get_prev(self, current_audio_path: str, current_time: float):
        """
        Метод API, при нажатии кнопки влево мы вызываем этот
        метод, передавая в сигнатуру текущий путь проигрываемого
        MP3-фрагмента и время от начала проигрывания
        """
        match self._nav_option:
            case NavOption.PHRASE:
                return self._get_prev_phrase(current_audio_path, current_time)
            case NavOption.HEADING:
                ...
            case NavOption.PAGE:
                ...

    def _get_next_heading(self, current_audio_path: str, current_time: float) -> Optional[NavText]:
        """Ищет audio тэг, в интервал которого попадает current_time.\n
        Например, мы передали current_audio_path = 823_r.mp3, current_time = 453.
        Соответствующий audio тег:
        <audio src="823_r.mp3" clip-begin="npt=451.216s" clip-end="npt=453.219s" id="rgn_aud_0823_0337" />.
        Сохраняем его положение в тексте. Соответствующий smil: s0823.smil\n
        1. Смотрим в ncc.html на наличие тегов h* в этом smil. Находим:
        ['<h2 id="cn23541"><a href="s0823.smil#tx24767">R</a></h2>']\n
        2. Ищем элемент с id=tx24767 в файле s0823.smil. Он находится раньше
        (по положению в тексте), а, значит, не подходит нам\n
        3. Ищем следующий заголовок в ncc.html, это
        <h2 id="cn23881"><a href="s0824.smil#tx25109">S</a></h2>.
        Т.к. он из следующего smil - это то, что нам нужно. Берем название: S\n
        4. Переходим в s0824.smil и ищем элемент с id=tx25109
        <text src="fp2003_rearmatter.html#cn23881" id="tx25109" />\n
        5. Находим следующий audio тег
        <audio src="824_s.mp3" clip-begin="npt=0.000s" clip-end="npt=0.569s" id="rgn_aud_0824_0001" />
        """
        smil_content, position, smil_name = self._get_smil_content_position_name(current_audio_path)
        matches = re.finditer(patterns['get_audio_info'], smil_content)
        for match in matches:
            clip_begin = float(match.group(2))
            clip_end = float(match.group(3))
            if clip_begin <= current_time < clip_end:
                position_in_text = match.start()  # Позиция кусочка аудио, интервал которого включает current_time
                smil_headings = self.find_headings_by_prefix(smil_name)
                last_h_position: int = 0  # Сохраняем позицию последнего заголовка, чтобы продолжить искать с нее
                for h in smil_headings:
                    h_href, h_text = h.group(1), h.group(
                        2)  # Получаем ссылку вида "s0823.smil#tx24767" и текст вида "R"
                    h_smil_name, h_text_id = h_href.split('#')
                    id_position: int = self.get_id_position_in_text(h_text_id, smil_content)
                    if id_position > position_in_text:  # Текст заголовка находится после конкретного match
                        # Ищем следующий audio тег с позиции id_position
                        next_match = re.search(patterns['get_audio_info'], smil_content[id_position:])
                        if next_match:
                            phrase: NavPhrase = NavPhrase(current_audio_path, float(next_match.group(2)),
                                                          float(next_match.group(3)))
                            nav_text: NavText = NavText(h_text, phrase)
                            return nav_text
                    last_h_position = h.start()
                # Итак, мы не нашли подходящего заголовка в этом smil, идем в пункт 3
                next_heading = self.find_next_heading_from_position(last_h_position)
                if next_heading:  # А может у нас уже был последний заголовок
                    h_href, h_text = next_heading.group(1), next_heading.group(
                        2)  # Получаем ссылку вида "s0823.smil#tx24767" и текст вида "R"
                    h_smil_name, h_text_id = h_href.split('#')
                    next_smil_content = self.try_open(self.get_smil_path(h_smil_name))
                    next_audio_path: str = self.find_audio_name(self.get_smil_path(h_smil_name))
                    next_id_position: int = self.get_id_position_in_text(h_text_id, next_smil_content)
                    next_audio_match = re.search(patterns['get_audio_info'], next_smil_content[next_id_position:])
                    if next_audio_match:
                        phrase: NavPhrase = NavPhrase(next_audio_path, float(next_audio_match.group(2)),
                                                      float(next_audio_match.group(3)))
                        nav_text: NavText = NavText(h_text, phrase)
                        return nav_text

    def _get_next_phrase(self, current_audio_path: str, current_time: float) -> Optional[NavPhrase]:
        """Ищет audio тэг, в интервал которого попадает current_time.\n
        1. Для следующего audio тега возвращает имя mp3, время начала и время конца.\n
        2. Если следующий audio тег не найден - ищет в следующем по порядку smil файле.\n
        3. Если первоначальный smil был последним - возвращает None"""
        smil_content, position, _ = self._get_smil_content_position_name(current_audio_path)
        matches = re.finditer(patterns['get_audio_info'], smil_content)
        for match in matches:
            clip_begin = float(match.group(2))
            clip_end = float(match.group(3))
            if clip_begin <= current_time < clip_end:
                try:
                    next_match = next(matches)
                    return NavPhrase(next_match.group(1), float(next_match.group(2)),
                                     float(next_match.group(3)))  # 1 вариант
                except StopIteration:
                    next_audio_path: str = self._positions_audios.get(position + 1)
                    if next_audio_path:
                        next_smil_content, _, _ = self._get_smil_content_position_name(next_audio_path)
                        next_audio_info = re.search(patterns['get_audio_info'], next_smil_content)
                        if next_audio_info:
                            return NavPhrase(next_audio_info.group(1), float(next_audio_info.group(2)),
                                             float(next_audio_info.group(3)))  # 2 вариант

    def _get_prev_phrase(self, current_audio_path: str, current_time: float) -> Optional[NavPhrase]:
        """Ищет audio тэг, в интервал которого попадает current_time.\n
        1. Для предыдущего audio тега возвращает имя mp3, время начала и время конца.\n
        2. Если предыдущий audio тег не найден - ищет в предыдущем по порядку smil файле.\n
        3. Если первоначальный smil был первым - возвращает None"""
        check_first_audio: bool = True
        smil_content, position, _ = self._get_smil_content_position_name(current_audio_path)
        matches = re.finditer(patterns['get_audio_info'], smil_content)
        for match, next_match in self._pairwise(matches):
            if check_first_audio:
                clip_begin = float(match.group(2))
                clip_end = float(match.group(3))
                if clip_begin <= current_time < clip_end:
                    if position > 1:
                        prev_audio_path: str = self._positions_audios.get(position - 1)
                        if prev_audio_path:
                            prev_smil_content, _, _ = self._get_smil_content_position_name(prev_audio_path)
                            next_matches = re.finditer(patterns['get_audio_info'], prev_smil_content)
                            *_, last = next_matches
                            return NavPhrase(last.group(1), float(last.group(2)), float(last.group(3)))  # 2 вариант
            if next_match:
                clip_begin = float(next_match.group(2))
                clip_end = float(next_match.group(3))
                if clip_begin <= current_time < clip_end:
                    return NavPhrase(match.group(1), float(match.group(2)), float(match.group(3)))  # 1 вариант

    @staticmethod
    def _pairwise(iterable):
        """Выдает пару элементов из итератора, чтобы иметь возможность осуществлять поиск в предыдущем значении"""
        a, b = itertools.tee(iterable)
        next(b, None)
        return zip(a, b)

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
parser.set_nav_option(NavOption.HEADING)

start_time = time.time()
nav_heading_1: NavText = parser.get_next("823_r.mp3", 456.5)
print(nav_heading_1.text)
print(nav_heading_1.next_phrase.__dict__)
nav_heading_2: NavText = parser.get_next(nav_heading_1.next_phrase.audio_path, nav_heading_1.next_phrase.start_time)
print(nav_heading_2.text)
print(nav_heading_2.next_phrase.__dict__)
nav_heading_3: NavText = parser.get_next(nav_heading_2.next_phrase.audio_path, nav_heading_2.next_phrase.start_time)
print(nav_heading_3.text)
print(nav_heading_3.next_phrase.__dict__)
end_time = time.time()
print(f"Время между 3 запросами: {end_time - start_time}")

parser.set_nav_option(NavOption.PHRASE)

start_time = time.time()
nav_phrase_1: NavPhrase = parser.get_next("823_r.mp3", 456.5)
print(nav_phrase_1.__dict__)
nav_phrase_2: NavPhrase = parser.get_next(nav_phrase_1.audio_path, nav_phrase_1.start_time)
print(nav_phrase_2.__dict__)
nav_phrase_3: NavPhrase = parser.get_next(nav_phrase_2.audio_path, nav_phrase_2.start_time)
print(nav_phrase_3.__dict__)
end_time = time.time()
print(f"Время между 3 запросами: {end_time - start_time}")

print('\n\n\n')

start_time = time.time()
nav_phrase_2: NavPhrase = parser.get_prev(nav_phrase_3.audio_path, nav_phrase_3.start_time)
print(nav_phrase_2.__dict__)
nav_phrase_1: NavPhrase = parser.get_prev(nav_phrase_2.audio_path, nav_phrase_2.start_time)
print(nav_phrase_1.__dict__)
nav_phrase_0: NavPhrase = parser.get_prev(nav_phrase_1.audio_path, nav_phrase_1.start_time)
print(nav_phrase_0.__dict__)
end_time = time.time()
print(f"Время между 3 запросами: {end_time - start_time}")


