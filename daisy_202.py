from typing import Optional, List
import re

from general import NavItem


def _get_nav_from_match_v202(phrase_match: re.Match, heading_text: str = '') -> Optional[NavItem]:
    src = phrase_match.group(1)
    time_begin = float(phrase_match.group(2))
    time_end = float(phrase_match.group(3))
    return NavItem(src, time_begin, time_end, heading_text)


def find_headings_list_by_smil_name(ncc_content: str, smil_name: str) -> List:
    pattern = rf'<h[1-6][^>].*?><a href="{smil_name}#([^"].*?)">([^<].*?)</a></h[1-6]>'
    return re.findall(pattern, ncc_content, re.DOTALL)


def find_pages_list_by_smil_name(ncc_content: str, smil_name: str) -> List:
    pattern = rf'<span[^>].*?><a href="{smil_name}#([^"].*?)">([^<].*?)</a></span>'
    return re.findall(pattern, ncc_content)


