import os.path
import time
from typing import Optional, Tuple, Dict, Iterator, Union, Literal
import re
from collections import OrderedDict

from daisy_30 import _get_smil_name_from_manifest, _get_nav_page_heading_from_match, _get_nav_phrase_from_match
from general import patterns, NavItem, NavOption, DAISY_VERSIONS, get_id_position_in_text, find_audio_name, _pairwise, \
    try_open, time_str_to_seconds, _pairwise_list


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
    _ncx_name: Optional[str]
    _ncx_content: Optional[str]
    _page_list_block: Optional[list]
    _nav_map_block: str
    _heading_list_block: Optional[list]
    _search_blocks: dict

    def __init__(self, folder_path: str):
        self._opf_name = None
        self._ncx_name = None
        self._page_list_block = None
        self._heading_list_block = None
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

    def _get_next_phrase_v3(self, current_audio_path: str, current_time: float) -> Optional[NavItem]:
        """
        1. Получаем соответствующий smil
        2. Получаем аудио в этом smil с подходящим интервалом
        3. Если есть следующая фраза - возвращаем ее
        4. Если нет следующей фразы - возвращаем первую фразу из следующего smil
        5. Если нет следующего smil - возвращаем None
        """
        result = self._audios_smils.get(current_audio_path)
        if not result:
            raise ValueError(f'Техническая ошибка: по каким-либо причинам файлу {current_audio_path} не присвоен соответствующий smil')
        received_audio_index, current_smil_name = result
        current_smil_content = try_open(f'{self.folder_path}/{current_smil_name}')
        smil_audios_iter = re.finditer(patterns['get_smil_audio_list'], current_smil_content, re.DOTALL)
        for cur, nex in _pairwise(smil_audios_iter):
            cur_begin_match = re.search(patterns['get_clip_begin'], cur.group(1))
            cur_end_match = re.search(patterns['get_clip_end'], cur.group(1))
            if cur_begin_match and cur_end_match:
                cur_begin = time_str_to_seconds(cur_begin_match.group(1))
                cur_end = time_str_to_seconds(cur_end_match.group(1))
                if cur_begin <= current_time < cur_end:
                    nav_item: NavItem = _get_nav_phrase_from_match(nex)
                    return nav_item
        next_audio_path = self._positions_audios.get(received_audio_index + 1)
        if not next_audio_path:
            raise ValueError(f'Текущая фраза по пути {current_audio_path} и временем {current_time} является последней')
        next_result = self._audios_smils.get(next_audio_path)
        _, next_smil_name = next_result
        next_smil_content = try_open(f'{self.folder_path}/{next_smil_name}')
        first_audio_in_next_smil = re.search(patterns['get_smil_audio_list'], next_smil_content, re.DOTALL)
        if first_audio_in_next_smil:
            nav_item: NavItem = _get_nav_phrase_from_match(first_audio_in_next_smil)
            return nav_item

    def _get_prev_phrase_v3(self, current_audio_path: str, current_time: float) -> Optional[NavItem]:
        result = self._audios_smils.get(current_audio_path)
        if not result:
            raise ValueError(f'Техническая ошибка: по каким-либо причинам файлу {current_audio_path} не присвоен соответствующий smil')
        received_audio_index, current_smil_name = result
        current_smil_content = try_open(f'{self.folder_path}/{current_smil_name}')
        smil_audios_iter = re.finditer(patterns['get_smil_audio_list'], current_smil_content, re.DOTALL)
        for cur, nex in _pairwise(smil_audios_iter):
            nex_begin_match = re.search(patterns['get_clip_begin'], nex.group(1))
            nex_end_match = re.search(patterns['get_clip_end'], nex.group(1))
            if nex_begin_match and nex_end_match:
                nex_begin = time_str_to_seconds(nex_begin_match.group(1))
                nex_end = time_str_to_seconds(nex_end_match.group(1))
                if nex_begin <= current_time < nex_end:
                    nav_item: NavItem = _get_nav_phrase_from_match(cur)
                    return nav_item
        prev_audio_path = self._positions_audios.get(received_audio_index - 1)
        if not prev_audio_path:
            raise ValueError(f'Текущая фраза по пути {current_audio_path} и временем {current_time} является первой')
        prev_result = self._audios_smils.get(prev_audio_path)
        _, prev_smil_name = prev_result
        prev_smil_content = try_open(f'{self.folder_path}/{prev_smil_name}')
        *_, last_audio_in_next_smil = re.finditer(patterns['get_smil_audio_list'], prev_smil_content, re.DOTALL)
        if last_audio_in_next_smil:
            nav_item: NavItem = _get_nav_phrase_from_match(last_audio_in_next_smil)
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
                            nav_item = _get_nav_page_heading_from_match(cur)
                            return nav_item
                elif self.get_audio_path_index(cur_src) > received_audio_index:
                    nav_item = _get_nav_page_heading_from_match(cur)
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
                            nav_item = _get_nav_page_heading_from_match(nex)
                            return nav_item
                        else:
                            nav_item = _get_nav_page_heading_from_match(cur)
                            return nav_item
                elif self.get_audio_path_index(nex_src) > received_audio_index:
                    nav_item = _get_nav_page_heading_from_match(cur)
                    return nav_item

    def get_audios_list(self):
        sorted_keys = iter(sorted(self._positions_audios))
        return [self._positions_audios.get(key) for key in sorted_keys]

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
        for first, second in _pairwise(audio_matches):
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
                smil_names = list(OrderedDict.fromkeys(re.findall(patterns['get_smil_name'], self._ncc_content)))
                current_smil_position: int = 1
                for smil_id in smil_names:
                    if corresponding_audio_name := find_audio_name(self.get_smil_path(smil_id)):
                        self._positions_audios[current_smil_position] = corresponding_audio_name
                        self._audios_smils[corresponding_audio_name] = current_smil_position, smil_id
                        current_smil_position += 1
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
                    ordered_smil_ids = re.finditer(patterns['get_spine_ordered_items'], spine_block.group(0))
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

    def _get_smil_content_position_name(self, audio_path: str) -> Tuple[str, int, str]:
        position, smil_name = self._audios_smils.get(audio_path)
        if not position or not smil_name:
            raise ValueError(f"Данному mp3-файлу {audio_path} не присвоен соответствующий smil")
        return try_open(self.get_smil_path(smil_name)), position, smil_name

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
                        return self._get_next_phrase(current_audio_path, current_time)
                    case '3.0':
                        return self._get_next_phrase_v3(current_audio_path, current_time)
            case NavOption.HEADING:
                match self.version:
                    case '2.02':
                        return self._get_next_heading(current_audio_path, current_time)
                    case '3.0':
                        return self._get_next_page_heading_v3(current_audio_path, current_time)
            case NavOption.PAGE:
                match self.version:
                    case '2.02':
                        return self._get_next_page(current_audio_path, current_time)
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
                        return self._get_prev_phrase(current_audio_path, current_time)
                    case '3.0':
                        return self._get_prev_phrase_v3(current_audio_path, current_time)
            case NavOption.HEADING:
                match self.version:
                    case '2.02':
                        return self._get_prev_heading(current_audio_path, current_time)
                    case '3.0':
                        return self._get_prev_page_heading_v3(current_audio_path, current_time)
            case NavOption.PAGE:
                match self.version:
                    case '2.02':
                        return self._get_prev_page(current_audio_path, current_time)
                    case '3.0':
                        return self._get_prev_page_heading_v3(current_audio_path, current_time)

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
                p_text_id_smil_pos = get_id_position_in_text(p_text_id, search_smil_content)
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
            for first, second in _pairwise(smil_pages):
                p_text_id, p_text = second.group(1).split('#')[-1], second.group(2)
                p_text_id_pos: int = get_id_position_in_text(p_text_id, start_smil_content)
                if p_text_id_pos > prev_audio_pos:
                    current_span_match = first
                    break
            start_audio_path = self._positions_audios.get(start_position - 1)
            if not start_audio_path:
                return None
            start_position, start_smil_name = self._audios_smils.get(start_audio_path)
            start_smil_content = try_open(self.get_smil_path(start_smil_name))

        if current_span_match:
            current_span_match_text_id, current_span_match_text = current_span_match.group(1).split('#')[
                -1], current_span_match.group(2)
            current_span_match_text_id_pos: int = get_id_position_in_text(current_span_match_text_id,
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
                    id_position: int = get_id_position_in_text(h_text_id, smil_content)
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
                    next_smil_content = try_open(self.get_smil_path(h_smil_name))
                    next_audio_path: str = find_audio_name(self.get_smil_path(h_smil_name))
                    next_id_position: int = get_id_position_in_text(h_text_id, next_smil_content)
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
                h_text_id_pos: int = get_id_position_in_text(h_text_id, smil_content)
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
        h_text_id_pos_in_smil: int = get_id_position_in_text(h_text_id, prev_smil_content)
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
        for match, next_match in _pairwise(matches):
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
