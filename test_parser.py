import time

from general import NavOption, NavItem
from parser import DaisyParser


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


def test_book_v3(folder_path: str, audio_path: str, current_time: float):
    parser = DaisyParser(folder_path)

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

    start_time = time.time()
    nav_page_3: NavItem = parser.get_prev(audio_path, current_time)
    print(nav_page_3.__dict__)
    nav_page_2: NavItem = parser.get_prev(nav_page_3.audio_path, nav_page_3.start_time)
    print(nav_page_2.__dict__)
    nav_page_1: NavItem = parser.get_prev(nav_page_2.audio_path, nav_page_2.start_time)
    print(nav_page_1.__dict__)
    end_time = time.time()
    print(f"Время между 3 запросами: {end_time - start_time}\n")

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
    nav_page_3: NavItem = parser.get_prev(audio_path, current_time)
    print(nav_page_3.__dict__)
    nav_page_2: NavItem = parser.get_prev(nav_page_3.audio_path, nav_page_3.start_time)
    print(nav_page_2.__dict__)
    nav_page_1: NavItem = parser.get_prev(nav_page_2.audio_path, nav_page_2.start_time)
    print(nav_page_1.__dict__)
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


FRONTPAGE = ['frontpage', '823_r.mp3', 456.5]
TEST_BOOK = ['test_book', '08_26th_.mp3', 263]
DAISY_3 = ['daisy_3', 'speechgen0007.mp3', 13]

# test_book(*FRONTPAGE)
test_book_v3(*DAISY_3)
