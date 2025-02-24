import io
import time
import uuid
from typing import Callable, Optional


class ProgressReader:
    def __init__(self, fp: io.BytesIO, callback: Callable[[int], None]):
        self.fp = fp
        self.callback = callback
        self.total = self._get_total()
        self.last_percent = 0

    def _get_total(self):
        current = self.fp.tell()
        self.fp.seek(0, io.SEEK_END)
        total = self.fp.tell()
        self.fp.seek(current, io.SEEK_SET)
        return total

    def read(self, size=-1):
        chunk = self.fp.read(size)
        pos = self.fp.tell()
        # Calculate the current progress percentage
        percent = int((pos / self.total) * 100) if self.total else 100
        if percent > self.last_percent:
            self.last_percent = percent
            self.callback(percent)
        return chunk

    def seek(self, offset, whence=io.SEEK_SET):
        return self.fp.seek(offset, whence)

    def tell(self):
        return self.fp.tell()

    def __len__(self):
        # Helps libraries like requests determine the size of the content
        return self.total

    def __getattr__(self, name):
        # Delegate attribute access to the underlying file object
        return getattr(self.fp, name)




import io
import os
import requests
from requests_toolbelt import MultipartEncoder, MultipartEncoderMonitor

ALLOWED_MAX_FILE_SIZE_BYTES = 500 * 1024 * 1024  # 500 MB in bytes


def upload0x0(file_path: str, filename: str, callback: Callable[[int], None] = lambda p: None) -> str:
    last_percent = 0

    def progress_callback(monitor):
        nonlocal last_percent
        p = int((monitor.bytes_read / monitor.len) * 100)
        if p > last_percent:
            last_percent = p
            callback(p)

    with open(file_path, "rb") as file_obj:
        file_obj.seek(0)
        encoder = MultipartEncoder(fields={"file": (filename, file_obj)})
        monitor = MultipartEncoderMonitor(encoder, progress_callback)
        response = requests.post("https://0x0.st", data=monitor, headers={"Content-Type": monitor.content_type})
        response.raise_for_status()
        return response.text.strip()


def upload_file(file_size_bytes: int, file_path: str, filename: str,
                callback: Callable[[int], None] = lambda p: None) -> str:
    threshold = 500 * 1024 * 1024  # 500 MB in bytes
    file_size_mb = file_size_bytes / (1024 * 1024)  # Convert bytes to megabytes

    if file_size_bytes <= threshold:
        print(f'Uploading {filename} of size {file_size_mb:.2f}MB to 0x0 anonfiles...')
        return upload0x0(file_path, filename, callback)

    return ""


def download(url: str, progress_callback: Optional[Callable[[int], None]] = None) -> str:
    # Use a context manager to ensure the response is properly closed.
    with requests.get(url, stream=True) as response:
        response.raise_for_status()

        total_size = int(response.headers.get('content-length', 0))
        chunk_size = 1024  # You can adjust this chunk size if needed.
        bytes_read = 0
        last_reported = 0

        filename = str(uuid.uuid4())  # Changed from uuid.uuid4().time to uuid.uuid4() for uniqueness.
        # Create download directory if it doesn't exist.
        download_dir = "/tmp/downloads"
        os.makedirs(download_dir, exist_ok=True)
        full_path = os.path.join(download_dir, filename)

        # Report 0% progress at the start.
        if progress_callback:
            progress_callback(0)

        with open(full_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:  # filter out keep-alive new chunks
                    f.write(chunk)
                    bytes_read += len(chunk)
                    if total_size:
                        percentage = int((bytes_read / total_size) * 100)
                        if percentage > last_reported:
                            last_reported = percentage
                            if progress_callback:
                                progress_callback(percentage)

        # Ensure 100% progress is reported.
        if progress_callback and last_reported < 100:
            progress_callback(100)

    # Delete all files older than 1 day (86400 seconds) from the download folder.
    current_time = time.time()
    for file in os.listdir(download_dir):
        file_path = os.path.join(download_dir, file)
        if os.path.isfile(file_path):
            if current_time - os.path.getmtime(file_path) > 86400:
                os.remove(file_path)

    return full_path

if __name__ == "__main__":
    path = "/Users/alex/Downloads/ISLP.pdf"  # Source file path.
    name = "file.pdf"  # Explicit filename for the upload.
    print("Uploading file...")
    try:
        url = upload_anonfiles(path, name, callback=lambda p: print(f"Uploaded {p}%"))
        print("File uploaded successfully. URL:", url if url else "Upload failed")
    except Exception as e:
        print("An error occurred:", e)