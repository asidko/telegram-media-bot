import dataclasses
import hashlib
import os
import threading
import time
from collections import deque
from dataclasses import dataclass, field

import dotenv
import telebot
from cachetools import TTLCache

from jackett import search_jackett
from localization import localized
from torrent_provider import get_torrent_info_by_magnet_link
from torrserver import get_file_as_link
from torrent import create_magnet_link_from_url

dotenv.load_dotenv()

bot = telebot.TeleBot(os.getenv('BOT_TOKEN'))

results_cache = TTLCache(maxsize=10000, ttl=2_592_000)  # cache for 30 days

MAX_QUERY_TEXT_LENGTH = 255
WAIT_TIMEOUT_TO_NOTIFY_SECONDS = 15
search_execution_times = deque(maxlen=5)


def get_average_search_execution_time():
    return round(sum(search_execution_times) / len(search_execution_times)) if search_execution_times else 0


@dataclass
class ResponseControl:
    title: str = ""
    action_key: str = ""
    action_url: str = ""


@dataclass
class UserResponse:
    user_id: int
    message: str = ""
    controls: list[ResponseControl] = field(default_factory=list)
    files: list = field(default_factory=list)


@dataclass
class ResponseFile:
    file_name: str = ""
    file_bytes: bytes = ""


@bot.message_handler(regexp="^/start")
def select(message):
    say(UserResponse(
        user_id=message.from_user.id,
        message=localized(message, 'start_message')
    ))


@bot.message_handler(regexp="^/test_upload")
def select(message):
    print("Getting a file")
    file_bytes = get_file_as_link('92656c49d99a3b30eee6d66b614d8d15afcaa794', 1)
    print("Sending file")
    bot.send_document(message.from_user.id, file_bytes, visible_file_name='test')



@bot.message_handler(regexp="^/select")
def select(message):
    print("Received message from: %s, text: %s" % (message.from_user.id, message.text))
    select_key = message.text.split("/select_")[1]

    selected_result = find_item_by_select_key(select_key)

    if selected_result is None:
        return say(UserResponse(
            user_id=message.from_user.id,
            message=localized(message, 'option_not_found')
        ))

    title = selected_result["title"]
    size = selected_result["size"]
    seeds = selected_result["seeds"]
    tracker = selected_result["tracker"] or 'Unknown tracker'
    magnet_link = selected_result["magnet"]
    torrent_link = selected_result["torrent"]

    # Create magnet link from torrent of not present
    magnet_link_from_torrent, is_torrent_file_present, torrent_file_content = create_magnet_link_from_url(torrent_link)
    if torrent_link and not magnet_link:
        magnet_link = magnet_link_from_torrent if magnet_link_from_torrent else localized(message,
                                                                                          'missing_magnet_link')

    # Upload torrent file document
    torrent_file_bytes = torrent_file_content if is_torrent_file_present else None

    html_hex = f'<a href="{magnet_link}">&#129522; Your magnet link</a>'.encode('utf-8').hex()

    user_response = UserResponse(user_id=message.from_user.id,
                                 message=f'<b>{title}</b>\n\n📄️{size} 🌱{seeds} 🏁<i>{tracker}</i>',
                                 controls=[ResponseControl(title=localized(message, 'magnet_link'),
                                                           action_url=f'https://asidko.github.io/html-render/?title=Download%20link&content={html_hex}')],
                                 files=[ResponseFile(file_name=f'{title}.torrent', file_bytes=torrent_file_bytes)])
    message_id = say(user_response)

    def edit_response_with_updated_data(current_response, message_id, torrent_info):
        new_message = current_response.message
        new_message += f'\n\n🗂️Files in torrent:\n'
        new_message += '<code>'
        limit = 10
        for f in torrent_info.files:
            if (limit := limit - 1) < 0:
                new_message += '...'
                break
            new_message += f'{f.size} {f.title}\n'
        new_message += '</code>'

        new_response = dataclasses.replace(current_response, message=new_message)
        say(new_response, message_id)

    get_torrent_info_by_magnet_link(magnet_link, lambda torrent_info: edit_response_with_updated_data(user_response,
                                                                                                      message_id,
                                                                                                      torrent_info))


def find_item_by_select_key(select_key):
    query_cache_key, item_id = select_key.split('_')
    results = results_cache.get(query_cache_key, [])
    return next((result for result in results if result['id'] == item_id), None)


# handle button click
@bot.callback_query_handler(func=lambda call: True)
def handle_query(call):
    command, query_hash = call.data.split(':')
    results = results_cache.get(query_hash, [])

    if not results:
        return say(UserResponse(
            user_id=call.from_user.id,
            message=localized(call, 'search_expired')
        ))

    if command == "filter_less_size_2":
        title = localized(call, 'filter_less_than_2gb')
        results = list(filter(lambda x: x['size_bytes'] < 2 * 1024 * 1024 * 1024, results))
        print_query_results(query_hash, call, results, title)
        return

    if command == "filter_more_size_4":
        title = localized(call, 'filter_more_than_4gb')
        results = list(filter(lambda x: x['size_bytes'] > 4 * 1024 * 1024 * 1024, results))
        print_query_results(query_hash, call, results, title)
        return

    if command == "filter_more_size_10":
        title = localized(call, 'filter_more_than_10gb')
        results = list(filter(lambda x: x['size_bytes'] > 10 * 1024 * 1024 * 1024, results))
        print_query_results(query_hash, call, results, title)
        return


def say(response: UserResponse, message_id_to_edit=None) -> int:
    keyboard = None

    if len(response.controls) > 0:
        keyboard = telebot.types.InlineKeyboardMarkup(row_width=2)
        for control in response.controls:
            params = {'text': control.title, 'callback_data': control.action_key} if control.action_key else {
                'text': control.title, 'url': control.action_url}
            keyboard.add(telebot.types.InlineKeyboardButton(**params))

    if message_id_to_edit is None:
        message = bot.send_message(response.user_id, response.message, parse_mode="HTML", reply_markup=keyboard)
    else:
        message = bot.edit_message_text(response.message, response.user_id, message_id_to_edit, parse_mode="HTML",
                                        reply_markup=keyboard)

    for file in response.files:
        if file.file_bytes:
            bot.send_document(response.user_id, file.file_bytes, visible_file_name=file.file_name)

    return message.message_id


@bot.message_handler(content_types=['text'], regexp="^[^/]")
def get_text_messages(message):
    text = message.text

    print("Received message from: %s, text: %s" % (message.from_user.id, message.text))

    say(UserResponse(
        user_id=message.from_user.id,
        message=localized(message, 'searching_for', text)
    ))

    text = clean_text(text)
    results = threaded_search_jackett(text, message)
    query_hash = hashlib.md5(text.encode()).hexdigest()
    results_cache[query_hash] = results

    if not results:
        return say(UserResponse(
            user_id=message.from_user.id,
            message=localized(message, 'nothing_found')
        ))

    print_query_results(query_hash, message, results, localized(message, 'results_by_popularity'))


def threaded_search_jackett(text, message) -> list[dict]:
    start_time = time.time()
    result = []

    def run_search():
        nonlocal result
        result = search_jackett(text)

    search_thread = threading.Thread(target=run_search)
    search_thread.start()

    # Start a separate thread to log a warning message after 8 seconds
    def say_warning():
        time.sleep(WAIT_TIMEOUT_TO_NOTIFY_SECONDS)
        if search_thread.is_alive():

            average_time = get_average_search_execution_time()

            if average_time < WAIT_TIMEOUT_TO_NOTIFY_SECONDS:
                alert = localized(message, 'search_time_alert_takes_longer')
            else:
                alert = localized(message, 'search_time_alert', average_time)

            say(UserResponse(
                user_id=message.from_user.id,
                message=alert
            ))

    alert_thread = threading.Thread(target=say_warning)
    alert_thread.start()

    search_thread.join()
    alert_thread.join()

    end_time_seconds = time.time() - start_time
    if end_time_seconds >= 5:  # ignore fast cached searches
        search_execution_times.append(end_time_seconds)

    return result


def clean_text(text):
    text = text[:MAX_QUERY_TEXT_LENGTH]
    text = text.lower().strip()
    return text


def print_query_results(query_hash, message, results, title_to_show):
    def make_row(result):
        id = result.get('id')
        title = result.get('title')
        size = result.get('size')
        seeds = result.get('seeds')
        tracker = result.get('tracker')
        command = f"/select_{query_hash}_{id}"
        m_t_indicator = "Ⓜ" if result.get('magnet') else ""
        m_t_indicator += "Ⓣ" if result.get('torrent') else ""

        return f"{title}\n{command}\n📄️{size} 🌱{seeds} 🏁<i>{tracker}</i> {m_t_indicator}\n\n"

    result_message = title_to_show + "\n\n"
    for result in results:
        row = make_row(result)
        if len(result_message) + len(row) > 4096:
            break
        result_message += row

    controls = create_filter_controls(query_hash, message, results)
    say(UserResponse(
        user_id=message.from_user.id,
        message=result_message,
        controls=controls
    ))


def create_filter_controls(query_hash, message, results) -> list[ResponseControl]:
    sizes_gb = [result['size_bytes'] / (1024 ** 3) for result in results if result['size_bytes']]
    hasLessThan2GB = any(size < 2 for size in sizes_gb)
    hasMoreThan4GB = any(size > 4 for size in sizes_gb)
    hasMoreThan10GB = any(size > 10 for size in sizes_gb)
    allAreLessThan2GB = all(size < 2 for size in sizes_gb)
    allAreMoreThan4GB = all(size > 4 for size in sizes_gb)
    allAreMoreThan10GB = all(size > 10 for size in sizes_gb)

    controls = []
    if hasLessThan2GB and not allAreLessThan2GB:
        controls.append(
            ResponseControl(title=localized(message, 'less_than_2_gb'), action_key=f"filter_less_size_2:{query_hash}"))
    if hasMoreThan4GB and not allAreMoreThan4GB:
        controls.append(
            ResponseControl(title=localized(message, 'more_than_4_gb'), action_key=f"filter_more_size_4:{query_hash}"))
    if hasMoreThan10GB and not allAreMoreThan10GB:
        controls.append(ResponseControl(title=localized(message, 'more_than_10_gb'),
                                        action_key=f"filter_more_size_10:{query_hash}"))
    return controls


bot.infinity_polling(timeout=60, long_polling_timeout=2)
