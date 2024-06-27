import itertools
import glob
import os.path
import time
from enum import IntEnum
from typing import Optional, Tuple, Dict, Iterator, Union, Literal
import re
from collections import OrderedDict

DAISY_VERSIONS = ['2.0', '2.02', '3.0']


class NavOption(IntEnum):
    PHRASE = 0
    HEADING = 1
    PAGE = 2


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


patterns = {
    'get_audio_src': r'<audio[^>]*\ssrc="([^"]+)"',  # Получаем значение атрибута src в теге audio
    'get_smil_name': r'href="([^"]+\.smil)#',  # Получаем название smil из ncc.html в виде s0002.smil
    'get_audio_info': r'<audio[^>]*src="([^"]+)"[^>]*clip-begin="npt=([0-9]+(?:\.[0-9]*)?)s"[^>]*clip-end="npt=([0-9]+(?:\.[0-9]*)?)s"[^>]*>',
    # Получаем временной интервал'
    'get_all_pages': r'<span class="[^"]*" id="[^"]*"><a href="([^"]*)">([^<]*)</a></span>',
    # Получаем список всех страниц
    # INFO: шаблоны для 3 версии
    'get_spine_content': r'<spine>(.*?)</spine>',  # Получаем содержимое блока spine
    'get_spine_ordered_items': r'idref="(.*?)"',  # Получаем список id smil по порядку в виде ['smil-1', smil-2'...]
    'get_manifest_content': r'<manifest>(.*?)</manifest>',  # Получаем блок, в котором получим названия smil
}


class DaisyParser:
    """
    Будем считать, что отдельный smil относится к
    отдельному MP3-фрагменту. Такая логика даже в
    600Мб файле на 835 страниц.
    """
    version: str
    folder_path: str
    _nav_option: NavOption
    _audios_smils: Dict[str, Tuple[
        int, str]]  # Словарь, где ключ - путь к аудиофайлу, а значение - массив с позицией данного файла и соответствующим именем smil
    _positions_audios: Dict[
        int, str]  # Словарь где мы храним порядковый номер каждого аудио как ключ и путь к аудио - как значение
    _ncc_content: Optional[str]
    _opf_name: Optional[str]
    _opf_content: Optional[str]

    def __init__(self, folder_path: str):
        version = '2.02' if os.path.exists(f'{folder_path}/ncc.html') else '3.0'
        self.set_daisy_version(version)
        start_time = time.time()
        self.folder_path = folder_path
        self._nav_option = NavOption.PHRASE
        self._audios_smils = {}
        """Словарь, ключ - путь к mp3, значение - (порядковый номер аудио, имя smil)"""
        self._positions_audios = {}
        """Словарь, ключ - порядковый номер аудио, значение - путь к mp3"""
        self._prepare_dicts()
        end_time = time.time()
        print(f'\nTotal parse time: {end_time - start_time:0.4f} seconds\n')

    def get_audios_list(self):
        sorted_keys = iter(sorted(self._positions_audios))
        return [self._positions_audios.get(key) for key in sorted_keys]

    def _get_smil_name_from_manifest(self, manifest_content: str, smil_id: str) -> str:
        pattern = rf'<item href="([^"]+)" id="{smil_id}".*?/>'
        smil_name = re.search(pattern, manifest_content, re.DOTALL)
        if not smil_name:
            raise ValueError(f'В манифесте файла пакета {self._opf_name} отсутствует smil с id = {smil_id}')
        return smil_name.group(1)

    def find_headings_by_prefix(self, smil_name: str) -> Iterator[re.Match[str]]:
        """Получить итератор заголовков, встречающихся в файле smil со smil_name"""
        pattern = rf'<h[1-6] id="[^"]*"><a href="({smil_name}[^"]*)">([^<]*)</a></h[1-6]>'
        matches = re.finditer(pattern, self._ncc_content)
        return matches

    def find_pages_by_prefix(self, smil_name: str) -> Iterator[re.Match[str]]:
        """Получить итератор страниц, встречающихся в файле smil со smil_name"""
        pattern = rf'<span class="[^"]*" id="[^"]*"><a href="({smil_name}[^"]*)">([^<]*)</a></span>'
        matches = re.finditer(pattern, self._ncc_content)
        return matches

    def _get_next_prev_audio_chunk_pos(self, audio_path: str, current_time: float,
                                       direction: Union[Literal[1], Literal[-1]] = 1) -> Optional[Tuple[int, str]]:
        """Получает положение аудио кусочка в соответствующем smil\n
        (предыдущего или следующего, в зависимости от direction) и\n
        название аудио либо None, если аудио кусочек был самым\n
        последним (direction = 1) или самым первым (direction = -1)"""
        audio_chunk_pos = None
        smil_content, smil_position, _ = self._get_smil_content_position_name(audio_path)
        audio_matches = re.finditer(patterns['get_audio_info'], smil_content)
        for first, second in self._pairwise(audio_matches):
            current, selected = (first, second) if direction == 1 else (second, first)
            clip_begin = float(current.group(2))
            clip_end = float(current.group(3))
            if clip_begin <= current_time < clip_end:
                audio_chunk_pos = selected.start()
                return audio_chunk_pos, audio_path
        if audio_chunk_pos is None:  # Тогда берем последний в предыдущем или первый в следующем mp3 файле
            next_position = smil_position + direction
            next_audio_path = self._positions_audios.get(next_position)
            if not next_audio_path:
                return None
            next_smil_content, _, _ = self._get_smil_content_position_name(next_audio_path)
            if direction == -1:
                try:
                    next_audio_matches = re.finditer(patterns['get_audio_info'], next_smil_content)
                    *_, last_audio_match_in_prev_audio_path = next_audio_matches
                    return last_audio_match_in_prev_audio_path.start(), next_audio_path
                except ValueError:
                    return None
            else:
                first_audio_match_in_next_audio_path = re.search(patterns['get_audio_info'], next_smil_content)
                return first_audio_match_in_next_audio_path.start(), next_audio_path

    def find_next_prev_heading_from_position(self, position: int, direction: Union[Literal[1], Literal[-1]] = 1) -> \
            Optional[re.Match[str]]:
        """По умолчанию ищет следующий заголовок после position в ncc.html\n
        Если direction = -1 - ищет предыдущий заголовок до position"""
        ncc_content = self._ncc_content[position + 1:] if direction == 1 else self._ncc_content[:position]
        pattern = r'<h[1-6] id="[^"]*"><a href="([^"]*)">([^<]*)</a></h[1-6]>'
        next_match = re.search(pattern, ncc_content)
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
        match self.version:
            case '2.02':
                self._ncc_content = self.try_open(f"{self.folder_path}/ncc.html")
                smil_names = list(OrderedDict.fromkeys(re.findall(patterns['get_smil_name'], self._ncc_content)))
                current_smil_position: int = 1
                for smil_id in smil_names:
                    if corresponding_audio_name := self.find_audio_name(self.get_smil_path(smil_id)):
                        self._positions_audios[current_smil_position] = corresponding_audio_name
                        self._audios_smils[corresponding_audio_name] = current_smil_position, smil_id
                        current_smil_position += 1
            case '3.0':
                for file in os.listdir(self.folder_path):
                    # check only text files
                    if file.endswith('.opf'):
                        self._opf_name = file
                        break
                if not self._opf_name:
                    raise ValueError('Отсутствует файл пакета с расширением .opf')
                self._opf_content = self.try_open(f'{self.folder_path}/{self._opf_name}')
                manifest_block = re.search(patterns['get_manifest_content'], self._opf_content, re.DOTALL)
                spine_block = re.search(patterns['get_spine_content'], self._opf_content, re.DOTALL)
                if manifest_block and spine_block:
                    ordered_smil_ids = re.finditer(patterns['get_spine_ordered_items'], spine_block.group(0))
                    start_position: int = 1
                    positions_smils = {}
                    for smil_id in ordered_smil_ids:
                        smil_name = self._get_smil_name_from_manifest(manifest_block.group(0), smil_id.group(1))
                        positions_smils[start_position] = smil_name
                        start_position += 1
                    # Получили словарь, где ключ - позиция, значение - название smil
                    for pos, name in positions_smils.items():
                        if corresponding_audio_name := self.find_audio_name(self.get_smil_path(name)):
                            self._positions_audios[pos] = corresponding_audio_name
                            self._audios_smils[corresponding_audio_name] = pos, name

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

    def set_daisy_version(self, version: str):
        if version in DAISY_VERSIONS:
            self.version = version
        else:
            raise ValueError(f"Укажите версию DAISY: {DAISY_VERSIONS}")

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
                return self._get_next_page(current_audio_path, current_time)

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
                return self._get_prev_heading(current_audio_path, current_time)
            case NavOption.PAGE:
                return self._get_prev_page(current_audio_path, current_time)

    def _get_next_page(self, current_audio_path: str, current_time: float) -> Optional[NavItem]:
        """
        1) Получаем соответствующий smil и позицию соответствующего аудио кусочка
        2) Находим первый тэг span в ncc.html, соответствующий данному smil,
        получаем id элемента в теге span и ищем позицию этого id в данном smil
        3) Если тег из пункта 2 не найден или позиция из п.2 ниже позиции из п.1 - в цикле while прибавляем
        по 1 к позиции smil из п.1, пока в файле ncc.html не будет найден тег span, принадлежащий очередному smil
        4) Получаем id элемента в теге span
        5) Находим позицию элемента с id из п.4 в соответствующем smil
        6) Находим следующий тег audio и возвращаем соответствующий NavText
        """
        smil_content, position, smil_name = self._get_smil_content_position_name(current_audio_path)
        audio_chunk_pos: Optional[int] = None
        matches = re.finditer(patterns['get_audio_info'], smil_content)
        for match in matches:
            clip_begin = float(match.group(2))
            clip_end = float(match.group(3))
            if clip_begin <= current_time < clip_end:
                audio_chunk_pos = match.start()
                break

        search_smil_content, search_position, search_smil_name, search_audio_path = smil_content, position, smil_name, current_audio_path
        while search_audio_path is not None:
            smil_pages = self.find_pages_by_prefix(search_smil_name)
            for p in smil_pages:
                p_text_id, p_text = p.group(1).split('#')[-1], p.group(2)
                p_text_id_smil_pos = self.get_id_position_in_text(p_text_id, search_smil_content)
                if p_text_id_smil_pos > audio_chunk_pos:
                    next_audio_chunk = re.search(patterns['get_audio_info'], search_smil_content[p_text_id_smil_pos:])
                    nav_text: NavItem = NavItem(search_audio_path, float(next_audio_chunk.group(2)),
                                                float(next_audio_chunk.group(3)), p_text)
                    return nav_text
            # Обнуление
            audio_chunk_pos = 0
            search_audio_path = self._positions_audios.get(search_position + 1)
            search_position += 1
            search_smil_content, search_position, search_smil_name = self._get_smil_content_position_name(
                search_audio_path)

    def _get_prev_page(self, current_audio_path: str, current_time: float) -> Optional[NavItem]:
        """
        1) Получаем соответствующий smil соответствующего аудио кусочка
        2) Находим предыдущий аудио кусочек, получаем его позицию
        3) Проходим по тегам span в ncc.html, соответствующим текущему smil,
        получаем id элемента в теге span и ищем позицию этого id в данном smil
        3) Если теги из пункта 3 не найдены или их позиция из п.3 выше позиции из п.2 - в цикле while отнимаем
        1 от позиции smil из п.1, пока в файле ncc.html не будет найден тег span, принадлежащий очередному smil
        4) Получаем id элемента в теге span
        5) Находим позицию элемента с id из п.4 в соответствующем smil
        6) Находим следующий тег audio и возвращаем соответствующий NavText
        """

        result = self._get_next_prev_audio_chunk_pos(current_audio_path, current_time, -1)
        if not result:
            return None
        prev_audio_pos, prev_audio_path = result[0], result[1]
        prev_smil_content, prev_position, prev_smil_name = self._get_smil_content_position_name(prev_audio_path)
        current_span_match = None
        start_position = prev_position
        start_smil_name = prev_smil_name
        start_audio_path = prev_audio_path
        start_smil_content = prev_smil_content
        while start_position != 0:
            smil_pages = self.find_pages_by_prefix(start_smil_name)
            for first, second in self._pairwise(smil_pages):
                p_text_id, p_text = second.group(1).split('#')[-1], second.group(2)
                p_text_id_pos: int = self.get_id_position_in_text(p_text_id, start_smil_content)
                if p_text_id_pos > prev_audio_pos:
                    current_span_match = first
                    break
            start_audio_path = self._positions_audios.get(start_position - 1)
            if not start_audio_path:
                return None
            start_position, start_smil_name = self._audios_smils.get(start_audio_path)
            start_smil_content = self.try_open(self.get_smil_path(start_smil_name))

        if current_span_match:
            current_span_match_text_id, current_span_match_text = current_span_match.group(1).split('#')[
                -1], current_span_match.group(2)
            current_span_match_text_id_pos: int = self.get_id_position_in_text(current_span_match_text_id,
                                                                               start_smil_content)
            next_audio_chunk = re.search(patterns['get_audio_info'],
                                         start_smil_content[current_span_match_text_id_pos:])
            nav_text: NavItem = NavItem(start_audio_path, float(next_audio_chunk.group(2)),
                                        float(next_audio_chunk.group(3)), current_span_match_text)
            return nav_text

        # # 1) Находим соответствующий аудио кусочек в соответствующем smil (current_time в интервале) и берем позицию
        # smil_content, position, smil_name = self._get_smil_content_position_name(current_audio_path)
        # matches = re.finditer(patterns['get_audio_info'], smil_content)
        # audio_chunk_pos: Optional[int] = None
        # for match in matches:
        #     clip_begin = float(match.group(2))
        #     clip_end = float(match.group(3))
        #     if clip_begin <= current_time < clip_end:
        #         audio_chunk_pos = match.start()
        #         break
        # # 2) Находим предыдущий аудио кусочек в соответствующем smil. TODO: Если его нет - продолжаем с п.10
        # prev_audio_chunk_pos: Optional[int] = None
        # if audio_chunk_pos:
        #     matches = re.finditer(patterns['get_audio_info'], smil_content[:audio_chunk_pos])
        #     try:
        #         *_, last = matches
        #         if last:
        #             # 3) Сохраняем позицию (старт) кусочка из п.2
        #             prev_audio_chunk_pos = last.start()
        #     except ValueError:
        #         pass
        # if prev_audio_chunk_pos:
        #     # 4) Ищем в ncc.html страницы, принадлежащие smil из п.1
        #     smil_pages = self.find_pages_by_prefix(smil_name)
        #     # 5) Получаем из ссылки каждого страницы текст и id элемента в smil из п.1
        #     for p in smil_pages:
        #         p_text_id, p_text = p.group(1).split('#')[-1], p.group(2)
        #         # 6) Ищем позицию id из п.5 в smil из п.1
        #         p_text_id_pos: int = self.get_id_position_in_text(p_text_id, smil_content)
        #         # 7) Если позиция из п.6 выше позиции из п.3 - прерываем цикл. TODO Продолжаем с п.10
        #         if p_text_id_pos > prev_audio_chunk_pos:
        #             break
        #         # 8) Если позиция из п.6 ниже позиции из п.3 - находим в smil из п.1 следующий аудио кусочек,
        #         # начиная с позиции из п.6
        #         elif p_text_id_pos < prev_audio_chunk_pos:
        #             next_audio_chunk = re.search(patterns['get_audio_info'], smil_content[p_text_id_pos:])
        #             # 9) Возвращаем соответствующий NavText INFO: основной вариант окончен
        #             nav_text: NavText = NavText(p_text, current_audio_path, float(next_audio_chunk.group(2)),
        #                                         float(next_audio_chunk.group(3)))
        #             return nav_text
        # # 10) Находим предыдущий audio_path относительно current_audio_path. Если его нет - возвращаем None INFO: конец
        # search_position = position
        # prev_page, prev_audio_path, prev_smil_content, prev_smil_name = None, None, None, None
        # while search_position != 0:
        #     prev_audio_path = self._positions_audios.get(search_position - 1)
        #     if not prev_audio_path:
        #         return None
        #     # 11) Находим smil, соответствующий audio_path из п.10
        #     prev_smil_content, _, prev_smil_name = self._get_smil_content_position_name(prev_audio_path)
        #     # 12) Находим последнюю страницу, принадлежащий smil из п.11
        #     prev_smil_pages = self.find_pages_by_prefix(prev_smil_name)
        #     try:
        #         *_, prev_page = prev_smil_pages
        #         break
        #     except ValueError:
        #         pass
        # if not prev_page:
        #     return None
        # # 13) Получаем его текст и id элемента в smil из п.11
        # p_text_id, p_text = prev_page.group(1).split('#')[-1], prev_page.group(2)
        # # 14) Ищем позицию id из п.13 в smil из п.11
        # p_text_id_pos_in_smil: int = self.get_id_position_in_text(p_text_id, prev_smil_content)
        # # 15) Находим в smil из п.11 следующий аудио кусочек, начиная с позиции из п.14
        # next_audio_match = re.search(patterns['get_audio_info'], smil_content[p_text_id_pos_in_smil:])
        # # 16) Возвращаем соответствующий NavText INFO: конец
        # nav_text: NavText = NavText(p_text, prev_audio_path, float(next_audio_match.group(2)),
        #                             float(next_audio_match.group(3)))
        # return nav_text

    def _get_next_heading(self, current_audio_path: str, current_time: float) -> Optional[NavItem]:
        """
        Ищет audio тэг, в интервал которого попадает current_time.\n
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
                            nav_text: NavItem = NavItem(current_audio_path, float(next_match.group(2)),
                                                        float(next_match.group(3)), h_text)
                            return nav_text
                    last_h_position = h.start()
                # Итак, мы не нашли подходящего заголовка в этом smil, идем в пункт 3
                next_heading = self.find_next_prev_heading_from_position(last_h_position)
                if next_heading:  # А может у нас уже был последний заголовок
                    h_href, h_text = next_heading.group(1), next_heading.group(
                        2)  # Получаем ссылку вида "s0823.smil#tx24767" и текст вида "R"
                    h_smil_name, h_text_id = h_href.split('#')
                    next_smil_content = self.try_open(self.get_smil_path(h_smil_name))
                    next_audio_path: str = self.find_audio_name(self.get_smil_path(h_smil_name))
                    next_id_position: int = self.get_id_position_in_text(h_text_id, next_smil_content)
                    next_audio_match = re.search(patterns['get_audio_info'], next_smil_content[next_id_position:])
                    if next_audio_match:
                        nav_text: NavItem = NavItem(next_audio_path, float(next_audio_match.group(2)),
                                                    float(next_audio_match.group(3)), h_text)
                        return nav_text

    def _get_prev_heading(self, current_audio_path: str, current_time: float) -> Optional[NavItem]:
        """
        Ищет audio тэг, в интервал которого попадает current_time.\n
        Например, мы передали current_audio_path = 823_r.mp3, current_time = 453.
        Соответствующий audio тег:
        <audio src="823_r.mp3" clip-begin="npt=451.216s" clip-end="npt=453.219s" id="rgn_aud_0823_0337" />.
        Сохраняем его положение в тексте. Соответствующий smil: s0823.smil\n
        1. Смотрим в ncc.html на наличие тегов h* в этом smil. Находим:
        ['<h2 id="cn23541"><a href="s0823.smil#tx24767">R</a></h2>']. Сохраняем название: R\n
        2. Ищем элемент с id=tx24767 в файле s0823.smil. Он находится раньше
        (по положению в тексте), а, значит, отлично подходит
        <text src="fp2003_rearmatter.html#cn23541" id="tx24767" />\n
        3. Находим следующий audio тег
        <audio src="823_r.mp3" clip-begin="npt=0.000s" clip-end="npt=0.486s" id="rgn_aud_0823_0001" />\n
        """
        # 1) Находим соответствующий аудио кусочек в соответствующем smil (current_time в интервале) и берем позицию
        smil_content, position, smil_name = self._get_smil_content_position_name(current_audio_path)
        matches = re.finditer(patterns['get_audio_info'], smil_content)
        audio_chunk_pos: Optional[int] = None
        for match in matches:
            clip_begin = float(match.group(2))
            clip_end = float(match.group(3))
            if clip_begin <= current_time < clip_end:
                audio_chunk_pos = match.start()
                break
        # 2) Находим предыдущий аудио кусочек в соответствующем smil. TODO: Если его нет - продолжаем с п.10
        prev_audio_chunk_pos: Optional[int] = None
        if audio_chunk_pos:
            matches = re.finditer(patterns['get_audio_info'], smil_content[:audio_chunk_pos])
            try:
                *_, last = matches
                if last:
                    # 3) Сохраняем позицию (старт) кусочка из п.2
                    prev_audio_chunk_pos = last.start()
            except ValueError:
                pass
        if prev_audio_chunk_pos:
            # 4) Ищем в ncc.html заголовки, принадлежащие smil из п.1
            smil_headings = self.find_headings_by_prefix(smil_name)
            # 5) Получаем из ссылки каждого заголовка текст и id элемента в smil из п.1
            for h in smil_headings:
                h_text_id, h_text = h.group(1).split('#')[-1], h.group(2)
                # 6) Ищем позицию id из п.5 в smil из п.1
                h_text_id_pos: int = self.get_id_position_in_text(h_text_id, smil_content)
                # 7) Если позиция из п.6 выше позиции из п.3 - прерываем цикл. TODO Продолжаем с п.10
                if h_text_id_pos > prev_audio_chunk_pos:
                    break
                # 8) Если позиция из п.6 ниже позиции из п.3 - находим в smil из п.1 следующий аудио кусочек,
                # начиная с позиции из п.6
                elif h_text_id_pos < prev_audio_chunk_pos:
                    next_audio_chunk = re.search(patterns['get_audio_info'], smil_content[h_text_id_pos:])
                    # 9) Возвращаем соответствующий NavText INFO: основной вариант окончен
                    nav_text: NavItem = NavItem(current_audio_path, float(next_audio_chunk.group(2)),
                                                float(next_audio_chunk.group(3)), h_text)
                    return nav_text
        # 10) Находим предыдущий audio_path относительно current_audio_path. Если его нет - возвращаем None INFO: конец
        search_position = position
        prev_heading, prev_audio_path, prev_smil_content, prev_smil_name = None, None, None, None
        while search_position != 0:
            prev_audio_path = self._positions_audios.get(search_position - 1)
            if not prev_audio_path:
                return None
            # 11) Находим smil, соответствующий audio_path из п.10
            prev_smil_content, _, prev_smil_name = self._get_smil_content_position_name(prev_audio_path)
            # 12) Находим последний заголовок, принадлежащий smil из п.11
            prev_smil_headings = self.find_headings_by_prefix(prev_smil_name)
            *_, last = prev_smil_headings
            if last:
                prev_heading = last
                break
        if not prev_heading:
            return None
        # 13) Получаем его текст и id элемента в smil из п.11
        h_text_id, h_text = prev_heading.group(1).split('#')[-1], prev_heading.group(2)
        # 14) Ищем позицию id из п.13 в smil из п.11
        h_text_id_pos_in_smil: int = self.get_id_position_in_text(h_text_id, prev_smil_content)
        # 15) Находим в smil из п.11 следующий аудио кусочек, начиная с позиции из п.14
        next_audio_match = re.search(patterns['get_audio_info'], smil_content[h_text_id_pos_in_smil:])
        # 16) Возвращаем соответствующий NavText INFO: конец
        nav_text: NavItem = NavItem(prev_audio_path, float(next_audio_match.group(2)),
                                    float(next_audio_match.group(3)), h_text)
        return nav_text

    def _get_next_phrase(self, current_audio_path: str, current_time: float) -> Optional[NavItem]:
        """
        Ищет audio тэг, в интервал которого попадает current_time.\n
        1. Для следующего audio тега возвращает имя mp3, время начала и время конца.\n
        2. Если следующий audio тег не найден - ищет в следующем по порядку smil файле.\n
        3. Если первоначальный smil был последним - возвращает None
        """
        smil_content, position, _ = self._get_smil_content_position_name(current_audio_path)
        matches = re.finditer(patterns['get_audio_info'], smil_content)
        for match in matches:
            clip_begin = float(match.group(2))
            clip_end = float(match.group(3))
            if clip_begin <= current_time < clip_end:
                try:
                    next_match = next(matches)
                    return NavItem(next_match.group(1), float(next_match.group(2)),
                                   float(next_match.group(3)))  # 1 вариант
                except StopIteration:
                    next_audio_path: str = self._positions_audios.get(position + 1)
                    if next_audio_path:
                        next_smil_content, _, _ = self._get_smil_content_position_name(next_audio_path)
                        next_audio_info = re.search(patterns['get_audio_info'], next_smil_content)
                        if next_audio_info:
                            return NavItem(next_audio_info.group(1), float(next_audio_info.group(2)),
                                           float(next_audio_info.group(3)))  # 2 вариант

    def _get_prev_phrase(self, current_audio_path: str, current_time: float) -> Optional[NavItem]:
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
                            return NavItem(last.group(1), float(last.group(2)), float(last.group(3)))  # 2 вариант
            if next_match:
                clip_begin = float(next_match.group(2))
                clip_end = float(next_match.group(3))
                if clip_begin <= current_time < clip_end:
                    return NavItem(match.group(1), float(match.group(2)), float(match.group(3)))  # 1 вариант

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


# Тестировочная функция
def test_book(folder_path: str, audio_path: str, current_time: float):
    parser = DaisyParser(folder_path)

    parser.set_nav_option(NavOption.HEADING)

    start_time = time.time()
    nav_heading_1: NavItem = parser.get_next(audio_path, current_time)
    print(nav_heading_1.__dict__)
    nav_heading_2: NavItem = parser.get_next(nav_heading_1.audio_path, nav_heading_1.start_time)
    print(nav_heading_2.__dict__)
    nav_heading_3: NavItem = parser.get_next(nav_heading_2.audio_path, nav_heading_2.start_time)
    print(nav_heading_3.__dict__)
    end_time = time.time()
    print(f"Время между 3 запросами: {end_time - start_time}\n")

    start_time = time.time()
    nav_heading_3: NavItem = parser.get_prev(audio_path, current_time)
    print(nav_heading_3.__dict__)
    nav_heading_2: NavItem = parser.get_prev(nav_heading_3.audio_path, nav_heading_3.start_time)
    print(nav_heading_2.__dict__)
    nav_heading_1: NavItem = parser.get_prev(nav_heading_2.audio_path, nav_heading_2.start_time)
    print(nav_heading_1.__dict__)
    end_time = time.time()
    print(f"Время между 3 запросами: {end_time - start_time}\n")

    parser.set_nav_option(NavOption.PHRASE)

    start_time = time.time()
    nav_phrase_1: NavItem = parser.get_next(audio_path, current_time)
    print(nav_phrase_1.__dict__)
    nav_phrase_2: NavItem = parser.get_next(nav_phrase_1.audio_path, nav_phrase_1.start_time)
    print(nav_phrase_2.__dict__)
    nav_phrase_3: NavItem = parser.get_next(nav_phrase_2.audio_path, nav_phrase_2.start_time)
    print(nav_phrase_3.__dict__)
    end_time = time.time()
    print(f"Время между 3 запросами: {end_time - start_time}\n")

    start_time = time.time()
    nav_phrase_2: NavItem = parser.get_prev(audio_path, current_time)
    print(nav_phrase_2.__dict__)
    nav_phrase_1: NavItem = parser.get_prev(nav_phrase_2.audio_path, nav_phrase_2.start_time)
    print(nav_phrase_1.__dict__)
    nav_phrase_0: NavItem = parser.get_prev(nav_phrase_1.audio_path, nav_phrase_1.start_time)
    print(nav_phrase_0.__dict__)
    end_time = time.time()
    print(f"Время между 3 запросами: {end_time - start_time}\n")

    parser.set_nav_option(NavOption.PAGE)

    start_time = time.time()
    nav_page_1: NavItem = parser.get_next(audio_path, current_time)
    print(nav_page_1.__dict__)
    nav_page_2: NavItem = parser.get_next(nav_page_1.audio_path, nav_page_1.start_time)
    print(nav_page_2.__dict__)
    nav_page_3: NavItem = parser.get_next(nav_page_2.audio_path, nav_page_2.start_time)
    print(nav_page_3.__dict__)
    end_time = time.time()
    print(f"Время между 3 запросами: {end_time - start_time}\n")

    # start_time = time.time()
    # nav_page_3: NavText = parser.get_prev(audio_path, current_time)
    # print(nav_page_3.__dict__)
    # nav_page_2: NavText = parser.get_prev(nav_page_3.audio_path, nav_page_3.start_time)
    # print(nav_page_2.__dict__)
    # nav_page_1: NavText = parser.get_prev(nav_page_2.audio_path, nav_page_2.start_time)
    # print(nav_page_1.__dict__)
    # end_time = time.time()
    # print(f"Время между 3 запросами: {end_time - start_time}\n")


FRONTPAGE = ['frontpage', '823_r.mp3', 456.5]
TEST_BOOK = ['test_book', '08_26th_.mp3', 263]

# test_book(*FRONTPAGE)
parser = DaisyParser('daisy_3')
print(parser.get_audios_list())