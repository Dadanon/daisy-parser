import time
from typing import Callable, Optional

from general import NavOption, NavItem, DIRECTION
from parser import DaisyParser


def _test_nav_option(parser: DaisyParser, audio_path: str, current_time: float, nav_option: NavOption, direction: DIRECTION = 1):
    print(f'\nТестируется навигация для {nav_option.name} в направлении {"вперед" if direction == 1 else "назад"}\n')
    func: Callable[[str, float], Optional[NavItem]] = parser.get_next if direction == 1 else parser.get_prev
    parser.set_nav_option(nav_option)
    start_time = time.time()
    nav_item_1: NavItem = func(audio_path, current_time)
    print(nav_item_1.__dict__ if nav_item_1 else None)
    if nav_item_1:
        nav_item_2: NavItem = func(nav_item_1.audio_path, nav_item_1.start_time)
        print(nav_item_2.__dict__ if nav_item_2 else None)
        if nav_item_2:
            nav_item_3: NavItem = func(nav_item_2.audio_path, nav_item_2.start_time)
            print(nav_item_3.__dict__ if nav_item_3 else None)
            if nav_item_3:
                end_time = time.time()
                print(f"Время между 3 запросами: {end_time - start_time}\n")


def test_book(folder_path: str, audio_path: str, current_time: float):
    parser = DaisyParser(folder_path)
    print(parser.get_creator_and_title())
    print(parser.get_audios_dict())
    print(parser.get_total_time())

    _test_nav_option(parser, audio_path, current_time, NavOption.HEADING, 1)
    _test_nav_option(parser, audio_path, current_time, NavOption.HEADING, -1)
    _test_nav_option(parser, audio_path, current_time, NavOption.PHRASE, 1)
    _test_nav_option(parser, audio_path, current_time, NavOption.PHRASE, -1)
    _test_nav_option(parser, audio_path, current_time, NavOption.PAGE, 1)
    _test_nav_option(parser, audio_path, current_time, NavOption.PAGE, -1)
    _test_nav_option(parser, audio_path, current_time, NavOption.GROUP, 1)
    _test_nav_option(parser, audio_path, current_time, NavOption.GROUP, -1)


FRONTPAGE = ['frontpage', '823_r.mp3', 456.5]
TEST_BOOK = ['test_book', '08_26th_.mp3', 263]
DAISY_3 = ['daisy_3', 'speechgen0002.mp3', 36]
MOUNTAINS_SKIP = ['mountains_skip', 'bagw0014.mp3', 17]
RUBY = ['ruby', 'hotl0008.mp3', 15]
TEST_BOOK_WITH_GROUPS = ['test_book_with_groups', '06_19th_.mp3', 150]

test_book(*MOUNTAINS_SKIP)
