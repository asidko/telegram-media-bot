import io
import os
import zipfile
from typing import Optional, Callable
from urllib.parse import urlparse, urlunparse

import requests

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


def download(url: str, progress_callback: Optional[Callable[[int], None]] = None) -> io.BytesIO:
    response = requests.get(url, stream=True)
    response.raise_for_status()

    total_size = int(response.headers.get('content-length', 0))
    chunk_size = 1024  # You can adjust this chunk size if needed.
    bytes_read = 0
    last_reported = 0

    buffer = io.BytesIO()

    # Report 0% progress at the start.
    if progress_callback:
        progress_callback(0)

    for chunk in response.iter_content(chunk_size=chunk_size):
        if chunk:  # filter out keep-alive new chunks
            buffer.write(chunk)
            bytes_read += len(chunk)
            if total_size:
                # Calculate percentage completed.
                percentage = int((bytes_read / total_size) * 100)
                # Check if we've passed the next 1% threshold.
                if percentage > last_reported:
                    last_reported = percentage
                    progress_callback(last_reported)

    # Ensure 100% progress is reported.
    if progress_callback and last_reported < 100:
        progress_callback(100)

    buffer.seek(0)
    return buffer


def upload0x0(file_bytes: io.BytesIO, filename: str) -> str:
    file_bytes.seek(0)
    files = {'file': (filename, file_bytes)}
    response = requests.post("https://0x0.st", files=files)
    if response.status_code == 403:
        # If 403 zip and try again
        zipped_bytes = io.BytesIO()
        with zipfile.ZipFile(zipped_bytes, "w", zipfile.ZIP_DEFLATED) as zipf:
            file_bytes.seek(0)
            zipf.writestr(filename, file_bytes.read())
        zipped_bytes.seek(0)
        files = {'file': (f"{filename}.zip", zipped_bytes)}
        response = requests.post("https://0x0.st", files=files)
    response.raise_for_status()
    return response.text.strip()



def upload_anonfiles(file_bytes: io.BytesIO, filename: str) -> str:
    allowed = {".zip", ".rar", ".jpg", ".jpeg", ".png", ".gif"}
    _, ext = os.path.splitext(filename)
    if ext.lower() not in allowed:
        z = io.BytesIO()
        with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
            file_bytes.seek(0)
            zf.writestr(filename, file_bytes.read())
        z.seek(0)
        filename += ".zip"
        file_bytes = z
    file_bytes.seek(0)
    r = requests.post("https://www.anonfile.la/process/upload_file", files={"file": (filename, file_bytes)})
    r.raise_for_status()
    d = r.json()
    if not d.get("success"):
        raise Exception("Upload failed: " + d.get("message", "Unknown error"))
    return d["url"].strip()

def fix_filename(filename: str) -> str:
    """Fix the filename by replacing spaces, dots, and underscores with a dash and removing all other non-alphanumeric characters."""
    # Split to file name and extension
    filename, ext = os.path.splitext(filename)
    return ''.join(c if c.isalnum() else '-' if c in ' ._' else '' for c in filename) + ext
