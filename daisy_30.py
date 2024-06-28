import re
from typing import Optional, Any

from general import patterns, NavItem, time_str_to_seconds


def _get_smil_name_from_manifest(_opf_name: str, manifest_content: str, smil_id: str) -> str:
    pattern = rf'<item href="([^"]+)" id="{smil_id}".*?/>'
    smil_name = re.search(pattern, manifest_content, re.DOTALL)
    if not smil_name:
        raise ValueError(f'В манифесте файла пакета {_opf_name} отсутствует smil с id = {smil_id}')
    return smil_name.group(1)


def _get_nav_page_heading_from_match(page_match: Any) -> Optional[NavItem]:
    """Работает с _pairwise (match) и с _pairwise_list (tuple)"""
    if isinstance(page_match, tuple):
        text, page_audio_info = page_match[0].strip(), page_match[1]
    elif isinstance(page_match, re.Match):
        text, page_audio_info = page_match.group(1).strip(), page_match.group(2)
    else:
        raise ValueError(f'Невозможно получить NavItem из {page_match}')
    time_begin_str_match = re.search(patterns['get_clip_begin'], page_audio_info)
    time_end_str_match = re.search(patterns['get_clip_end'], page_audio_info)
    src_match = re.search(patterns['get_src'], page_audio_info)
    if time_begin_str_match and time_end_str_match and src_match:
        src = src_match.group(1)
        time_begin = time_str_to_seconds(time_begin_str_match.group(1))
        time_end = time_str_to_seconds(time_end_str_match.group(1))
        return NavItem(src, time_begin, time_end, text)


def _get_nav_phrase_from_match(phrase_match: re.Match) -> Optional[NavItem]:
    page_audio_info = phrase_match.group(1)
    time_begin_str_match = re.search(patterns['get_clip_begin'], page_audio_info)
    time_end_str_match = re.search(patterns['get_clip_end'], page_audio_info)
    src_match = re.search(patterns['get_src'], page_audio_info)
    if time_begin_str_match and time_end_str_match and src_match:
        src = src_match.group(1)
        time_begin = time_str_to_seconds(time_begin_str_match.group(1))
        time_end = time_str_to_seconds(time_end_str_match.group(1))
        return NavItem(src, time_begin, time_end)