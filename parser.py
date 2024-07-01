import os.path
import time
from typing import Optional, Tuple, Dict, Iterator, Union, Literal
import re
from collections import OrderedDict

from daisy_202 import _get_nav_from_match_v202, find_headings_pages_list_by_smil_name
from daisy_30 import _get_smil_name_from_manifest, _get_nav_page_heading_from_match_v30, _get_nav_phrase_from_match_v30
from general import patterns, NavItem, NavOption, DAISY_VERSIONS, get_id_position_in_text, find_audio_name, _pairwise, \
    try_open, time_str_to_seconds, _pairwise_list, DIRECTION


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
    _smils_positions: Dict[str, int]  # Словарь вида {'1.smil': 1, '2.smil': 2}
    _ncc_content: Optional[str]
    _opf_name: Optional[str]
    _opf_content: Optional[str]
    _ncx_name: Optional[str]
    _ncx_content: Optional[str]
    _page_list_block: Optional[list]
    _nav_map_block: str
    _heading_list_block: Optional[list]
    _search_blocks: dict
    _search_blocks_v2: dict
    _headings_list: Optional[Iterator[re.Match]]
    _pages_list: Optional[Iterator[re.Match]]

    def __init__(self, folder_path: str):
        self._opf_name = None
        self._ncx_name = None
        self._page_list_block = None
        self._heading_list_block = None
        self._headings_list = None
        self._pages_list = None
        self._smils_positions = {}
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
        self._search_blocks = {
            NavOption.HEADING: self._heading_list_block,
            NavOption.PAGE: self._page_list_block
        }
        self._search_blocks_v2 = {
            NavOption.HEADING: self._headings_list,
            NavOption.PAGE: self._pages_list
        }
        end_time = time.time()
        print(f'\nTotal parse time: {end_time - start_time:0.4f} seconds\n')

    def get_audio_path_index(self, audio_path: str) -> int:
        received_audio_index = None
        start_audio_index: int = 1
        while not received_audio_index:
            next_audio_path = self._positions_audios.get(start_audio_index)
            if next_audio_path == audio_path:
                return start_audio_index
            start_audio_index += 1
        if not received_audio_index:
            raise ValueError(f'Техническая ошибка: путь {audio_path} не в списке')

    def _get_first_phrase_result(self, current_audio_path: str, current_time: float, direction: DIRECTION = 1) -> Union[
        NavItem, int]:
        result = self._audios_smils.get(current_audio_path)
        if not result:
            raise ValueError(
                f'Техническая ошибка: по каким-либо причинам файлу {current_audio_path} не присвоен соответствующий smil')
        received_audio_index, current_smil_name = result
        current_smil_content = try_open(f'{self.folder_path}/{current_smil_name}')
        smil_audios_iter = re.finditer(patterns['get_smil_audio_list'], current_smil_content, re.DOTALL)
        for cur, nex in _pairwise(smil_audios_iter):
            current_item, next_item = (cur, nex) if direction == 1 else (nex, cur)
            cur_begin_match = re.search(patterns['get_clip_begin'], current_item.group(1))
            cur_end_match = re.search(patterns['get_clip_end'], current_item.group(1))
            if cur_begin_match and cur_end_match:
                cur_begin = time_str_to_seconds(cur_begin_match.group(1))
                cur_end = time_str_to_seconds(cur_end_match.group(1))
                if cur_begin <= current_time < cur_end:
                    nav_item: NavItem = _get_nav_phrase_from_match_v30(next_item)
                    return nav_item
        return received_audio_index

    def _get_next_phrase_v3(self, current_audio_path: str, current_time: float) -> Optional[NavItem]:
        """
        1. Получаем соответствующий smil
        2. Получаем аудио в этом smil с подходящим интервалом
        3. Если есть следующая фраза - возвращаем ее
        4. Если нет следующей фразы - возвращаем первую фразу из следующего smil
        5. Если нет следующего smil - возвращаем None
        """
        result: Union[NavItem, int] = self._get_first_phrase_result(current_audio_path, current_time, 1)
        if not isinstance(result, int):
            return result
        next_audio_path = self._positions_audios.get(result + 1)
        if not next_audio_path:
            return None
        next_result = self._audios_smils.get(next_audio_path)
        _, next_smil_name = next_result
        next_smil_content = try_open(f'{self.folder_path}/{next_smil_name}')
        first_audio_in_next_smil = re.search(patterns['get_smil_audio_list'], next_smil_content, re.DOTALL)
        if first_audio_in_next_smil:
            nav_item: NavItem = _get_nav_phrase_from_match_v30(first_audio_in_next_smil)
            return nav_item

    def _get_prev_phrase_v3(self, current_audio_path: str, current_time: float) -> Optional[NavItem]:
        result: Union[NavItem, int] = self._get_first_phrase_result(current_audio_path, current_time, -1)
        if not isinstance(result, int):
            return result
        prev_audio_path = self._positions_audios.get(result - 1)
        if not prev_audio_path:
            return None
        prev_result = self._audios_smils.get(prev_audio_path)
        _, prev_smil_name = prev_result
        prev_smil_content = try_open(f'{self.folder_path}/{prev_smil_name}')
        *_, last_audio_in_next_smil = re.finditer(patterns['get_smil_audio_list'], prev_smil_content, re.DOTALL)
        if last_audio_in_next_smil:
            nav_item: NavItem = _get_nav_phrase_from_match_v30(last_audio_in_next_smil)
            return nav_item

    def _get_next_page_heading_v3(self, current_audio_path: str, current_time: float):
        received_audio_index = self.get_audio_path_index(current_audio_path)
        for cur, nex in _pairwise_list(self._search_blocks.get(self._nav_option)):
            # Получаем аудио инфо в формате строки: clipBegin="0:00:34.218" clipEnd="0:00:35.388" src="speechgen0002.mp3"
            cur_nav_audio_info = cur[1]
            cur_src_match = re.search(patterns['get_src'], cur_nav_audio_info)
            if cur_src_match:
                cur_src = cur_src_match.group(1)
                if self.get_audio_path_index(cur_src) == received_audio_index:
                    cur_time_begin_str_match = re.search(patterns['get_clip_begin'], cur_nav_audio_info)
                    if cur_time_begin_str_match:
                        cur_time_begin = time_str_to_seconds(cur_time_begin_str_match.group(1))
                        if current_time < cur_time_begin:
                            nav_item = _get_nav_page_heading_from_match_v30(cur)
                            return nav_item
                elif self.get_audio_path_index(cur_src) > received_audio_index:
                    nav_item = _get_nav_page_heading_from_match_v30(cur)
                    return nav_item

    def _get_prev_page_heading_v3(self, current_audio_path: str, current_time: float) -> Optional[NavItem]:
        received_audio_index = self.get_audio_path_index(current_audio_path)
        for cur, nex in _pairwise_list(self._search_blocks.get(self._nav_option)):
            nex_page_audio_info = nex[1]
            nex_src_match = re.search(patterns['get_src'], nex_page_audio_info)
            if nex_src_match:
                nex_src = nex_src_match.group(1)
                if self.get_audio_path_index(nex_src) == received_audio_index:
                    nex_time_end_str_match = re.search(patterns['get_clip_end'], nex_page_audio_info)
                    if nex_time_end_str_match:
                        nex_time_end = time_str_to_seconds(nex_time_end_str_match.group(1))
                        if nex_time_end < current_time:
                            nav_item = _get_nav_page_heading_from_match_v30(nex)
                            return nav_item
                        else:
                            nav_item = _get_nav_page_heading_from_match_v30(cur)
                            return nav_item
                elif self.get_audio_path_index(nex_src) > received_audio_index:
                    nav_item = _get_nav_page_heading_from_match_v30(cur)
                    return nav_item

    def get_audios_list(self):
        sorted_keys = iter(sorted(self._positions_audios))
        return [self._positions_audios.get(key) for key in sorted_keys]

    def get_smil_path(self, smil_name: str):
        return f"{self.folder_path}/{smil_name}"

    def _prepare_dicts(self):
        """
        1) Получаем словарь позиция - путь аудио
        2) Получаем словарь путь аудио - (путь smil, позиция)
        """
        match self.version:
            case '2.02':
                self._ncc_content = try_open(f"{self.folder_path}/ncc.html")
                smil_names = list(OrderedDict.fromkeys(re.findall(patterns['get_smil_name'], self._ncc_content, re.DOTALL)))
                current_smil_position: int = 1
                for smil_id in smil_names:
                    if corresponding_audio_name := find_audio_name(self.get_smil_path(smil_id)):
                        self._smils_positions[smil_id] = current_smil_position
                        self._positions_audios[current_smil_position] = corresponding_audio_name
                        self._audios_smils[corresponding_audio_name] = current_smil_position, smil_id
                        current_smil_position += 1
                self._headings_list = re.finditer(patterns['get_headings'], self._ncc_content, re.DOTALL)
                self._pages_list = re.finditer(patterns['get_pages'], self._ncc_content, re.DOTALL)
            case '3.0':
                for file in os.listdir(self.folder_path):
                    # check only text files
                    if file.endswith('.opf'):
                        self._opf_name = file
                        if self._ncx_name:
                            break
                    if file.endswith('.ncx'):
                        self._ncx_name = file
                        if self._opf_name:
                            break
                if not self._opf_name:
                    raise ValueError('Отсутствует файл пакета с расширением .opf')
                if not self._ncx_name:
                    raise ValueError('Отсутствует файл пакета с расширением .ncx')
                self._opf_content = try_open(f'{self.folder_path}/{self._opf_name}')
                self._ncx_content = try_open(f'{self.folder_path}/{self._ncx_name}')
                self._page_list_block = re.findall(patterns['get_pages_list'], self._ncx_content, re.DOTALL)
                nav_map_block_match = re.search(patterns['get_nav_map_block'], self._ncx_content, re.DOTALL)
                if not nav_map_block_match:
                    raise ValueError('Отсутствует блок навигации, связанный с заголовками, в 3 версии')
                self._nav_map_block = nav_map_block_match.group(1)
                self._heading_list_block = re.findall(patterns['get_nav_points'], self._nav_map_block, re.DOTALL)
                manifest_block = re.search(patterns['get_manifest_content'], self._opf_content, re.DOTALL)
                spine_block = re.search(patterns['get_spine_content'], self._opf_content, re.DOTALL)
                if manifest_block and spine_block:
                    ordered_smil_ids = re.finditer(patterns['get_spine_ordered_items'], spine_block.group(0), re.DOTALL)
                    start_position: int = 1
                    positions_smils = {}
                    for smil_id in ordered_smil_ids:
                        smil_name = _get_smil_name_from_manifest(self._opf_name, manifest_block.group(0),
                                                                 smil_id.group(1))
                        positions_smils[start_position] = smil_name
                        start_position += 1
                    # Получили словарь, где ключ - позиция, значение - название smil
                    for pos, name in positions_smils.items():
                        if corresponding_audio_name := find_audio_name(self.get_smil_path(name)):
                            self._positions_audios[pos] = corresponding_audio_name
                            self._audios_smils[corresponding_audio_name] = pos, name

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

    def get_next(self, current_audio_path: str, current_time: float) -> Optional[NavItem]:
        """
        Метод API, при нажатии кнопки вправо мы вызываем этот
        метод, передавая в сигнатуру текущий путь проигрываемого
        MP3-фрагмента и время от начала проигрывания
        """
        match self._nav_option:
            case NavOption.PHRASE:
                match self.version:
                    case '2.02':
                        return self._get_next_prev_phrase(current_audio_path, current_time, 1)
                    case '3.0':
                        return self._get_next_phrase_v3(current_audio_path, current_time)
            case NavOption.HEADING:
                match self.version:
                    case '2.02':
                        return self._get_next_heading_page(current_audio_path, current_time)
                    case '3.0':
                        return self._get_next_page_heading_v3(current_audio_path, current_time)
            case NavOption.PAGE:
                match self.version:
                    case '2.02':
                        return self._get_next_heading_page(current_audio_path, current_time)
                    case '3.0':
                        return self._get_next_page_heading_v3(current_audio_path, current_time)

    def get_prev(self, current_audio_path: str, current_time: float) -> Optional[NavItem]:
        """
        Метод API, при нажатии кнопки влево мы вызываем этот
        метод, передавая в сигнатуру текущий путь проигрываемого
        MP3-фрагмента и время от начала проигрывания
        """
        match self._nav_option:
            case NavOption.PHRASE:
                match self.version:
                    case '2.02':
                        return self._get_next_prev_phrase(current_audio_path, current_time, -1)
                    case '3.0':
                        return self._get_prev_phrase_v3(current_audio_path, current_time)
            case NavOption.HEADING:
                match self.version:
                    case '2.02':
                        return self._get_prev_heading_page(current_audio_path, current_time)
                    case '3.0':
                        return self._get_prev_page_heading_v3(current_audio_path, current_time)
            case NavOption.PAGE:
                match self.version:
                    case '2.02':
                        return self._get_prev_heading_page(current_audio_path, current_time)
                    case '3.0':
                        return self._get_prev_page_heading_v3(current_audio_path, current_time)

    def _get_next_heading_page(self, current_audio_path: str, current_time: float) -> Optional[NavItem]:
        current_position, current_smil_name = self._audios_smils.get(current_audio_path)
        current_smil_navs = find_headings_pages_list_by_smil_name(self._ncc_content, current_smil_name,
                                                                  self._nav_option)
        if len(current_smil_navs) > 0:
            current_smil_content = try_open(self.get_smil_path(current_smil_name))
            for nav in current_smil_navs:
                nav_id = nav[0]
                nav_id_pos_in_smil = get_id_position_in_text(nav_id, current_smil_content, current_smil_name)
                nav_audio = re.search(patterns['get_audio_info'], current_smil_content[nav_id_pos_in_smil:], re.DOTALL)
                if nav_audio:
                    nav_audio_start = float(nav_audio.group(2))
                    if nav_audio_start > current_time:
                        nav_item: NavItem = _get_nav_from_match_v202(nav_audio, nav[1])
                        return nav_item
            start_position = current_position
            while start_position < len(self._positions_audios):
                nex_audio_path = self._positions_audios.get(start_position + 1)
                _, nex_smil_name = self._audios_smils.get(nex_audio_path)
                nex_smil_navs = find_headings_pages_list_by_smil_name(self._ncc_content, nex_smil_name, self._nav_option)
                if len(nex_smil_navs) > 0:
                    nex_nav = nex_smil_navs[0]
                    nex_smil_content = try_open(self.get_smil_path(nex_smil_name))
                    nex_nav_id = nex_nav[0]
                    nex_nav_id_pos_in_smil = get_id_position_in_text(nex_nav_id, nex_smil_content, nex_smil_name)
                    nex_nav_audio = re.search(patterns['get_audio_info'], nex_smil_content[nex_nav_id_pos_in_smil:], re.DOTALL)
                    if nex_nav_audio:
                        nex_nav_item: NavItem = _get_nav_from_match_v202(nex_nav_audio, nex_nav[1])
                        return nex_nav_item
                start_position += 1

    def _get_prev_heading_page(self, current_audio_path: str, current_time: float) -> Optional[NavItem]:
        current_position, current_smil_name = self._audios_smils.get(current_audio_path)
        current_smil_navs = find_headings_pages_list_by_smil_name(self._ncc_content, current_smil_name, self._nav_option)
        if len(current_smil_navs) > 0:
            # Найдены заголовки для соответствующего smil, начинаем искать с конца
            current_smil_content = try_open(self.get_smil_path(current_smil_name))
            for nav in reversed(current_smil_navs):
                nav_id = nav[0]
                nav_id_pos_in_smil = get_id_position_in_text(nav_id, current_smil_content, current_smil_name)
                nav_audio = re.search(patterns['get_audio_info'], current_smil_content[nav_id_pos_in_smil:], re.DOTALL)
                if nav_audio:
                    nav_audio_end = float(nav_audio.group(3))
                    if nav_audio_end < current_time:
                        nav_item: NavItem = _get_nav_from_match_v202(nav_audio, nav[1])
                        return nav_item
        # Не нашли подходящий заголовок для данного smil, ищем первый предыдущий
        start_position = current_position
        while start_position > 1:
            prev_audio_path = self._positions_audios.get(start_position - 1)
            if not prev_audio_path:
                return None
            _, prev_smil_name = self._audios_smils.get(prev_audio_path)
            prev_smil_navs = find_headings_pages_list_by_smil_name(self._ncc_content, prev_smil_name, self._nav_option)
            if len(prev_smil_navs) > 0:
                prev_heading = prev_smil_navs[-1]
                prev_smil_content = try_open(self.get_smil_path(prev_smil_name))
                nav_id = prev_heading[0]
                nav_id_pos_in_smil = get_id_position_in_text(nav_id, prev_smil_content, prev_smil_name)
                nav_audio = re.search(patterns['get_audio_info'], prev_smil_content[nav_id_pos_in_smil:], re.DOTALL)
                if nav_audio:
                    nav_item: NavItem = _get_nav_from_match_v202(nav_audio, prev_heading[1])
                    return nav_item
            start_position -= 1

    def _get_next_prev_phrase(self, current_audio_path: str, current_time: float, direction: DIRECTION = 1) -> Optional[
        NavItem]:
        current_audio_position, current_smil = self._audios_smils.get(current_audio_path)
        current_smil_content = try_open(f'{self.folder_path}/{current_smil}')
        current_smil_audios_iter = re.finditer(patterns['get_audio_info'], current_smil_content, re.DOTALL)
        for cur, nex in _pairwise(current_smil_audios_iter):
            current_phrase, next_phrase = (cur, nex) if direction == 1 else (nex, cur)
            cur_time_begin = float(current_phrase.group(2))
            cur_time_end = float(current_phrase.group(3))
            if cur_time_begin <= current_time < cur_time_end:
                nav_item: NavItem = _get_nav_from_match_v202(next_phrase)
                return nav_item
        next_audio_path = self._positions_audios.get(current_audio_position + direction)
        if not next_audio_path:
            return None
        _, next_smil = self._audios_smils.get(next_audio_path)
        next_smil_content = try_open(f'{self.folder_path}/{next_smil}')
        if direction == 1:
            next_phrase_match = re.search(patterns['get_audio_info'], next_smil_content, re.DOTALL)
        else:
            next_smil_phrases_iter = re.finditer(patterns['get_audio_info'], next_smil_content, re.DOTALL)
            *_, next_phrase_match = next_smil_phrases_iter
        if next_phrase_match:
            nav_item: NavItem = _get_nav_from_match_v202(next_phrase_match)
            return nav_item
