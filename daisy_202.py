from typing import Optional, List, Union, Literal
import re

from general import NavItem, patterns, NavOption


def _get_nav_from_match_v202(phrase_match: re.Match, heading_text: str = '') -> Optional[NavItem]:
    src = phrase_match.group(1)
    time_begin = float(phrase_match.group(2))
    time_end = float(phrase_match.group(3))
    return NavItem(src, time_begin, time_end, heading_text)


def find_headings_pages_list_by_smil_name(ncc_content: str, smil_name: str, nav_option: Union[Literal[NavOption.HEADING, NavOption.PAGE]]) -> List:
    match nav_option:
        case NavOption.HEADING:
            chunks = re.finditer(patterns['get_headings_new'], ncc_content, re.DOTALL)
        case NavOption.PAGE:
            chunks = re.finditer(patterns['get_pages_new'], ncc_content, re.DOTALL)
        case _:
            raise ValueError(f'Недопустимый формат nav_option: {nav_option}')
    nav_list = []
    for chunk in chunks:
        pattern = rf'<a href="{smil_name}#([^"].*?)">([^<].*?)</a>'
        result = re.search(pattern, chunk.group(0), re.DOTALL)
        if result:
            nav_list.append([result.group(1), result.group(2)])
    return nav_list


