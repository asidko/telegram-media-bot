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
from src.torrserver import torrserver_get_info
from torrserver import torrserver_get_file, torrserver_get_file_download_link
from utils import write_to_query_log, clean_text, remove_host_from_url, is_video, is_audio, get_file_icon, download
from torrent_provider import get_torrent_info_by_magnet_link, TorrentInfo, TorrentFileInfo
from torrent import create_magnet_link_from_url

# Load environment variables
dotenv.load_dotenv()

# Initialize bot and global configuration
BOT_TOKEN = os.getenv('BOT_TOKEN')
bot = telebot.TeleBot(BOT_TOKEN)
ADVERTISED_TORRSERVER_HOST = os.getenv('ADVERTISED_TORRSERVER_HOST')

# Global cache and constants
RESULTS_CACHE = TTLCache(maxsize=10000, ttl=2_592_000)  # 30 days
WAIT_TIMEOUT_TO_NOTIFY_SECONDS = 15
SEARCH_EXECUTION_TIMES = deque(maxlen=5)
TELEGRAM_DOCUMENT_UPLOAD_LIMIT_MB = int(os.getenv('TELEGRAM_DOCUMENT_UPLOAD_LIMIT_MB', 2000))


def get_average_search_execution_time() -> int:
    """Calculate average search time from recent executions."""
    if SEARCH_EXECUTION_TIMES:
        return round(sum(SEARCH_EXECUTION_TIMES) / len(SEARCH_EXECUTION_TIMES))
    return 0


# =============================================================================
# Data Classes
# =============================================================================
@dataclass
class ResponseControl:
    title: str = ""
    action_key: str = ""
    action_url: str = ""


@dataclass
class ResponseFile:
    file_name: str = ""
    file_bytes: bytes = b""


@dataclass
class UserResponse:
    user_id: int
    message: str = ""
    controls: list[ResponseControl] = field(default_factory=list)
    files: list[ResponseFile] = field(default_factory=list)


# =============================================================================
# Utility Functions
# =============================================================================
def say(response: UserResponse, message_id_to_edit: int = None) -> int:
    """Send or edit a message and send any attached files."""
    keyboard = None
    if response.controls:
        keyboard = telebot.types.InlineKeyboardMarkup(row_width=2)
        for control in response.controls:
            button_params = {'text': control.title}
            if control.action_key:
                button_params['callback_data'] = control.action_key
            else:
                button_params['url'] = control.action_url
            keyboard.add(telebot.types.InlineKeyboardButton(**button_params))

    if message_id_to_edit is None:
        message_obj = bot.send_message(
            response.user_id, response.message, parse_mode="HTML", reply_markup=keyboard
        )
    else:
        message_obj = bot.edit_message_text(
            response.message, response.user_id, message_id_to_edit, parse_mode="HTML", reply_markup=keyboard
        )

    for file in response.files:
        if file.file_bytes:
            bot.send_document(response.user_id, file.file_bytes, visible_file_name=file.file_name)

    return message_obj.message_id


def find_item_by_key(query_key: str, item_key: str) -> dict | None:
    """Retrieve an item from the cache based on query and item keys."""
    results = RESULTS_CACHE.get(query_key, [])
    return next((result for result in results if result.get('id') == item_key), None)


def create_filter_controls(query_hash: str, message, results: list[dict]) -> list[ResponseControl]:
    """Create filter buttons based on the sizes of results."""
    sizes_gb = [result['size_bytes'] / (1024 ** 3) for result in results if result.get('size_bytes')]
    controls = []
    if sizes_gb:
        has_less_than_2 = any(size < 2 for size in sizes_gb)
        all_less_than_2 = all(size < 2 for size in sizes_gb)
        has_more_than_4 = any(size > 4 for size in sizes_gb)
        all_more_than_4 = all(size > 4 for size in sizes_gb)
        has_more_than_10 = any(size > 10 for size in sizes_gb)
        all_more_than_10 = all(size > 10 for size in sizes_gb)

        if has_less_than_2 and not all_less_than_2:
            controls.append(ResponseControl(
                title=localized(message, 'less_than_2_gb'),
                action_key=f"filter_less_size_2:{query_hash}"
            ))
        if has_more_than_4 and not all_more_than_4:
            controls.append(ResponseControl(
                title=localized(message, 'more_than_4_gb'),
                action_key=f"filter_more_size_4:{query_hash}"
            ))
        if has_more_than_10 and not all_more_than_10:
            controls.append(ResponseControl(
                title=localized(message, 'more_than_10_gb'),
                action_key=f"filter_more_size_10:{query_hash}"
            ))
    return controls


def print_query_results(query_hash: str, message, results: list[dict], title_to_show: str) -> None:
    """Format and send the query results with optional filter controls."""

    def make_row(result: dict) -> str:
        item_id = result.get('id')
        title = result.get('title')
        size = result.get('size')
        seeds = result.get('seeds')
        tracker = result.get('tracker', 'Unknown tracker')
        command = f"/select_{query_hash}_{item_id}"
        indicators = ""
        if result.get('magnet'):
            indicators += "Ⓜ"
        if result.get('torrent'):
            indicators += "Ⓣ"
        return f"{title}\n{command}\n📄️{size} 🌱{seeds} 🏁<i>{tracker}</i> {indicators}\n\n"

    result_message = title_to_show + "\n\n"
    for result in results:
        row = make_row(result)
        if len(result_message) + len(row) > 4096:
            result_message += "..."
            break
        result_message += row

    controls = create_filter_controls(query_hash, message, results)
    say(UserResponse(
        user_id=message.from_user.id,
        message=result_message,
        controls=controls
    ))


# =============================================================================
# Bot Command Handlers
# =============================================================================
@bot.message_handler(regexp="^/start")
def handle_start(message):
    """Handle the /start command."""
    response = UserResponse(
        user_id=message.from_user.id,
        message=localized(message, 'start_message')
    )
    say(response)


@bot.message_handler(regexp="^/test_upload")
def handle_test_upload(message):
    """Handle the /test_upload command."""
    print("Getting a file")
    file_bytes = torrserver_get_file('92656c49d99a3b30eee6d66b614d8d15afcaa794', 1)
    print("Sending file")
    bot.send_document(message.from_user.id, file_bytes, visible_file_name='test')


@bot.message_handler(regexp="^/file")
def handle_file_command(message):
    """Process the /file command to send a download link for a specific file."""
    print(f"Received /file command from: {message.from_user.id}, text: {message.text}")
    try:
        select_value = message.text.split("/file_")[1]
        query_key, item_key, file_id = select_value.split('_')
    except (IndexError, ValueError):
        return say(UserResponse(
            user_id=message.from_user.id,
            message=localized(message, 'option_not_found')
        ))

    selected_result = find_item_by_key(query_key, item_key)
    if selected_result is None:
        return say(UserResponse(
            user_id=message.from_user.id,
            message=localized(message, 'option_not_found')
        ))

    magnet_link = selected_result.get("magnet_calculated")
    if not magnet_link:
        return say(UserResponse(
            user_id=message.from_user.id,
            message=localized(message, 'missing_magnet_link')
        ))

    def send_download_link(torrent_info: TorrentInfo, selected_file_id: str) -> None:
        torrent_hash = torrent_info.hash

        download_file: TorrentFileInfo = next(filter(lambda f: f.id == int(selected_file_id), torrent_info.files), None)
        if not download_file:
            say(UserResponse(user_id=message.from_user.id, message=localized(message, 'search_expired')))

        download_link_info = torrserver_get_file_download_link(torrent_hash, selected_file_id)
        full_link = ADVERTISED_TORRSERVER_HOST + remove_host_from_url(download_link_info.link)
        file_title = f'<code>{os.path.basename(download_file.title)}</code> - {download_file.size}'
        text = f"🥂{file_title}\n<pre>{full_link}</pre>"
        if is_video(file_title):
            text += f"\n<i>* {localized(message, 'paste_link_to_player_warning')}</i>"

        controls = [
            ResponseControl(title=localized(message, 'download'), action_url=full_link)
        ]

        can_upload_to_telegram = download_file.size_bytes < TELEGRAM_DOCUMENT_UPLOAD_LIMIT_MB * 1024 ** 2
        if can_upload_to_telegram:
            controls.append(ResponseControl(
                title=localized(message, '📩 Download to this chat'),
                action_key=f'telegram_download:{torrent_hash},{selected_file_id}'
            ))

        response = UserResponse(
            user_id=message.from_user.id,
            message=text,
            controls=controls
        )

        try:
            say(response)
        except Exception as e:
            print(f"Error showing download button: {e}")
            # Fallback without button controls
            say(dataclasses.replace(response, controls=[]))

    get_torrent_info_by_magnet_link(
        magnet_link,
        lambda torrent_info: send_download_link(torrent_info, file_id)
    )


@bot.message_handler(regexp="^/select")
def handle_select_command(message):
    """Handle the /select command and provide torrent details and file list."""
    print(f"Received /select command from: {message.from_user.id}, text: {message.text}")
    try:
        select_value = message.text.split("/select_")[1]
        query_key, item_key = select_value.split('_')
    except (IndexError, ValueError):
        return say(UserResponse(
            user_id=message.from_user.id,
            message=localized(message, 'option_not_found')
        ))

    selected_result = find_item_by_key(query_key, item_key)
    if selected_result is None:
        return say(UserResponse(
            user_id=message.from_user.id,
            message=localized(message, 'option_not_found')
        ))

    title = selected_result.get("title", "")
    size = selected_result.get("size", "")
    seeds = selected_result.get("seeds", "")
    tracker = selected_result.get("tracker") or 'Unknown tracker'
    magnet_link = selected_result.get("magnet")
    torrent_link = selected_result.get("torrent")

    # Generate magnet link from torrent if necessary
    magnet_link_from_torrent, is_torrent_file_present, torrent_file_content = create_magnet_link_from_url(torrent_link)
    if torrent_link and not magnet_link:
        magnet_link = magnet_link_from_torrent if magnet_link_from_torrent else localized(message,
                                                                                          'missing_magnet_link')
    selected_result["magnet_calculated"] = magnet_link

    torrent_file_bytes = torrent_file_content if is_torrent_file_present else None
    html_hex = f'<a href="{magnet_link}">&#129522; Your magnet link</a>'.encode('utf-8').hex()

    user_response = UserResponse(
        user_id=message.from_user.id,
        message=f'<b>{title}</b>\n\n📄️{size} 🌱{seeds} 🏁<i>{tracker}</i>',
        controls=[ResponseControl(
            title=localized(message, 'magnet_link'),
            action_url=f'https://asidko.github.io/html-render/?title=Download%20link&content={html_hex}'
        )],
        files=[ResponseFile(file_name=f'{title}.torrent', file_bytes=torrent_file_bytes)]
    )
    message_id = say(user_response)

    def edit_response_with_updated_data(current_response: UserResponse, msg_id: int, q_key: str, i_key: str,
                                        torrent_info) -> None:
        new_message = current_response.message + f'\n\n{localized(message, "files_in_torrent")}\n'
        limit = 25
        for file in torrent_info.files:
            limit -= 1
            if limit < 0:
                new_message += '...'
                break
            file_title = os.path.basename(file.title)
            file_icon = get_file_icon(file_title)
            new_message += f'/file_{q_key}_{i_key}_{file.id} {file_icon} {file_title} - {file.size}\n'
        updated_response = dataclasses.replace(current_response, message=new_message, files=[])
        say(updated_response, msg_id)

    def edit_response_with_alert(current_response: UserResponse, msg_id: int) -> None:
        new_message = current_response.message + f'\n\n{localized(message, "torrent_info_not_found")}'
        updated_response = dataclasses.replace(current_response, message=new_message, files=[])
        say(updated_response, msg_id)

    get_torrent_info_by_magnet_link(
        magnet_link,
        lambda torrent_info: edit_response_with_updated_data(user_response, message_id, query_key, item_key,
                                                             torrent_info),
        lambda: edit_response_with_alert(user_response, message_id)
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith('telegram_download:'))
def handle_telegram_download_callback_query(call):
    """Handle the callback query for downloading a file to the chat."""
    command, args = call.data.split(':')
    torrent_hash, file_id = args.split(',')

    link_info = torrserver_get_file_download_link(torrent_hash, file_id)
    progress_msg_id = say(UserResponse(
        user_id=call.from_user.id,
        message=localized(call, 'downloading_file', link_info.file_name)))

    last_notified_progress = 0
    def update_progress(progress: int):
        nonlocal last_notified_progress
        is_large_size = link_info.size_bytes > 200 * 1024 ** 2
        if not is_large_size and (progress - last_notified_progress) < 10:
            return
        last_notified_progress = progress
        say(UserResponse(
            user_id=call.from_user.id,
            message=localized(call, 'downloading_file_progress', link_info.file_name, progress),
        ), progress_msg_id)

    file_bytes = download(link_info.link, update_progress)

    uploading_tg_msg_id = say(UserResponse(
        user_id=call.from_user.id,
        message=localized(call, 'uploading_to_telegram', link_info.file_name),
    ))
    bot.send_document(call.from_user.id, file_bytes, visible_file_name=f'{link_info.file_name}', caption=f'{link_info.torrent_name}', timeout=3600)
    bot.delete_messages(call.from_user.id, [progress_msg_id, uploading_tg_msg_id])

@bot.callback_query_handler(func=lambda call: call.data.startswith('filter_'))
def handle_filter_callback_query(call):
    """Handle button callback queries for filtering results."""
    command, query_hash = call.data.split(':')
    results = RESULTS_CACHE.get(query_hash, [])
    if not results:
        return say(UserResponse(
            user_id=call.from_user.id,
            message=localized(call, 'search_expired')
        ))

    if command == "filter_less_size_2":
        title = localized(call, 'filter_less_than_2gb')
        filtered_results = [r for r in results if r.get('size_bytes', 0) < 2 * 1024 ** 3]
        print_query_results(query_hash, call, filtered_results, title)
    elif command == "filter_more_size_4":
        title = localized(call, 'filter_more_than_4gb')
        filtered_results = [r for r in results if r.get('size_bytes', 0) > 4 * 1024 ** 3]
        print_query_results(query_hash, call, filtered_results, title)
    elif command == "filter_more_size_10":
        title = localized(call, 'filter_more_than_10gb')
        filtered_results = [r for r in results if r.get('size_bytes', 0) > 10 * 1024 ** 3]
        print_query_results(query_hash, call, filtered_results, title)


@bot.message_handler(content_types=['text'], regexp="^[^/]")
def handle_text_message(message):
    """Handle plain text messages by performing a search."""
    print(f"Received text message from: {message.from_user.id}, text: {message.text}")
    isotime = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())
    user_id = message.from_user.id
    user_login = message.from_user.username
    write_to_query_log(f"{isotime} {user_id} {user_login} # {message.text}")

    say(UserResponse(
        user_id=user_id,
        message=localized(message, 'searching_for', message.text)
    ))

    cleaned_text = clean_text(message.text)
    results = threaded_search_jackett(cleaned_text, message)
    query_hash = hashlib.md5(cleaned_text.encode()).hexdigest().upper()[:6]
    RESULTS_CACHE[query_hash] = results

    if not results:
        return say(UserResponse(
            user_id=user_id,
            message=localized(message, 'nothing_found')
        ))

    print_query_results(query_hash, message, results, localized(message, 'results_by_popularity'))


def threaded_search_jackett(text: str, message) -> list[dict]:
    """Execute the search in a separate thread and notify if it takes too long."""
    start_time = time.time()
    search_results: list[dict] = []

    def run_search():
        nonlocal search_results
        try:
            search_results = search_jackett(text)
        except Exception as e:
            print(f"Error during search: {e}")

    search_thread = threading.Thread(target=run_search)
    search_thread.start()

    def notify_if_slow():
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

    alert_thread = threading.Thread(target=notify_if_slow)
    alert_thread.start()
    search_thread.join()

    elapsed_time = time.time() - start_time
    if elapsed_time >= 5:  # record only non-cached searches
        SEARCH_EXECUTION_TIMES.append(elapsed_time)
    return search_results


if __name__ == "__main__":
    bot.infinity_polling(timeout=60, long_polling_timeout=2)
