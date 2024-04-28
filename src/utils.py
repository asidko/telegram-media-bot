import os
from urllib.parse import urlparse, urlunparse

MAX_QUERY_TEXT_LENGTH = 255

def remove_host_from_url(url) -> str:
    parsed_url = urlparse(url)
    # Create a new URL with the scheme and netloc set to empty
    modified_url = parsed_url._replace(scheme='', netloc='')
    # Construct the URL without the scheme and netloc
    return str(urlunparse(modified_url))


def write_to_query_log(query):
    if not os.path.exists('logs'):
        os.makedirs('logs')

    with open('logs/query_log.txt', 'a') as file:
        file.write(f"{query}\n")

def is_video(file_title):
    return any(ext in file_title for ext in ['.mkv', '.mp4', '.avi', '.mov'])
def is_audio(file_title):
    return any(ext in file_title for ext in ['.mp3', '.flac', '.wav', '.m4a'])

def clean_text(text):
    text = text[:MAX_QUERY_TEXT_LENGTH]
    text = text.lower().strip()
    return text

def bytes_to_human_readable(size: int) -> str:
    if not size:
        return "(unknown size)"

    units = ['B', 'KB', 'MB', 'GB', 'TB']
    unit = units[0]  # default to bytes if less than 1024 bytes
    for unit in units:
        if size < 1024:
            break
        size /= 1024.0

    if unit in ['GB', 'TB']:
        return f"{size:.2f} {unit}"
    elif unit == 'B' and size < 1:
        return "1 KB"  # For sizes less than 1 KB, show as 1 KB
    else:
        return f"{int(size)} {unit}"  # Show integer values for B, KB, MB

def get_file_icon(file_title):
    file_icon = '▶'
    if is_audio(file_title):
        file_icon = '🎧'
    if is_video(file_title):
        file_icon = '🎬'
    return file_icon