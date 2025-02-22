import io
import os
import zipfile
import requests
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
import zipfile
import requests
from requests_toolbelt import MultipartEncoder, MultipartEncoderMonitor

def upload_anonfiles(file_bytes: io.BytesIO, filename: str, callback=lambda percent: None) -> str:
    allowed = {".zip", ".rar", ".jpg", ".jpeg", ".png", ".gif"}
    _, ext = os.path.splitext(filename)
    if ext.lower() not in allowed:
        # Create a ZIP file if the extension isn't allowed
        z = io.BytesIO()
        with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
            file_bytes.seek(0)
            zf.writestr(filename, file_bytes.read())
        z.seek(0)
        filename += ".zip"
        file_bytes = z

    file_bytes.seek(0)

    # Callback function to track the progress of the upload
    # Store last reported percent in a mutable container
    last_percent = 0

    def progress_callback(monitor):
        nonlocal last_percent
        percent = int((monitor.bytes_read / monitor.len) * 100)
        if percent > last_percent:
            last_percent = percent
            callback(percent)

    # Prepare multipart encoded data and wrap it with a monitor for progress tracking
    encoder = MultipartEncoder(
        fields={
            "file": (filename, file_bytes)
        }
    )
    monitor = MultipartEncoderMonitor(encoder, progress_callback)

    # Make the POST request with the monitored encoder
    try:
        r = requests.post(
            "https://www.anonfile.la/process/upload_file",
            data=monitor,
            headers={"Content-Type": monitor.content_type}
        )
        r.raise_for_status()
    except requests.RequestException as e:
        # Log HTTP error status and payload if available
        status = getattr(r, "status_code", "No response")
        response_text = getattr(r, "text", "")
        print(f"HTTP error occurred: {status} - {response_text}")
        return ""

    d = r.json()
    if not d.get("success"):
        raise Exception("Upload failed: " + d.get("message", "Unknown error"))
    return d["url"].strip()


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


if __name__ == "__main__":
    file_path = "/Users/alex/Downloads/WoR_Release_2.3.1.zip"
    with open(file_path, "rb") as f:
        file_bytes = io.BytesIO(f.read())

    print("Uploading file...")
    try:
        # Use a lambda to print the progress percentage
        url = upload_anonfiles(
            file_bytes,
            os.path.basename(file_path),
            callback=lambda percent: print(f"Uploaded {percent:.2f}%")
        )
        print("File uploaded successfully. URL:", url)
    except Exception as e:
        print("An error occurred:", e)