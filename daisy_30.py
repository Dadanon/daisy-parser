import re
from typing import Iterator, Optional

from general import patterns, NavItem, _pairwise


def _get_smil_name_from_manifest(_opf_name: str, manifest_content: str, smil_id: str) -> str:
    pattern = rf'<item href="([^"]+)" id="{smil_id}".*?/>'
    smil_name = re.search(pattern, manifest_content, re.DOTALL)
    if not smil_name:
        raise ValueError(f'В манифесте файла пакета {_opf_name} отсутствует smil с id = {smil_id}')
    return smil_name.group(1)
