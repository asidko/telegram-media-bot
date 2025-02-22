import io
import os
import tempfile
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


def upload_anonfiles(file_path: str, filename: str, callback: Callable[[int], None] = lambda p: None) -> str:
    allowed = {".zip", ".rar", ".jpg", ".jpeg", ".png", ".gif"}
    _, ext = os.path.splitext(filename)
    temp_zip_file = None

    # If the provided filename's extension is not allowed, create a temporary ZIP file.
    if ext.lower() not in allowed:
        temp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
        temp_zip_file = temp.name
        temp.close()  # Close so zipfile can write to it.
        with zipfile.ZipFile(temp_zip_file, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(file_path, arcname=filename)
        filename += ".zip"
        file_obj = open(temp_zip_file, "rb")
    else:
        file_obj = open(file_path, "rb")

    file_obj.seek(0)
    last_percent = 0

    def progress_callback(monitor):
        nonlocal last_percent
        p = int((monitor.bytes_read / monitor.len) * 100)
        if p > last_percent:
            last_percent = p
            callback(p)

    encoder = MultipartEncoder(fields={"file": (filename, file_obj)})
    monitor = MultipartEncoderMonitor(encoder, progress_callback)

    try:
        r = requests.post(
            "https://www.anonfile.la/process/upload_file",
            data=monitor,
            headers={"Content-Type": monitor.content_type},
            timeout=3600
        )
        r.raise_for_status()
        d = r.json()
        if not d.get("success"):
            raise Exception("Upload failed: " + d.get("message", "Unknown error"))
        return d["url"].strip()
    except requests.RequestException:
        status = getattr(r, "status_code", "No response")
        response_text = getattr(r, "text", "")
        print(f"HTTP error occurred: {status} - {response_text}")
        return ""
    finally:
        file_obj.close()
        if temp_zip_file is not None and os.path.exists(temp_zip_file):
            os.remove(temp_zip_file)

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
    path = "/Users/alex/Downloads/Rufus-4-6-Build-2205-BETA.exe"  # Source file path.
    name = "Rufus-4-6-Build-2205-BETA.exe.zip"  # Explicit filename for the upload.
    print("Uploading file...")
    try:
        url = upload_anonfiles(path, name, callback=lambda p: print(f"Uploaded {p}%"))
        print("File uploaded successfully. URL:", url if url else "Upload failed")
    except Exception as e:
        print("An error occurred:", e)