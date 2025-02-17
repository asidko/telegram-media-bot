import io
import json
import os
from io import BytesIO
from typing import TypedDict

import dotenv
import requests

dotenv.load_dotenv()

torrserver_url = os.getenv("TORRSERVER_URL")

class TorrserverFileStat(TypedDict):
    id: int
    path: str
    length: int

class TorrserverTorrent(TypedDict):
    title: str
    category: str
    poster: str
    timestamp: int
    name: str
    hash: str
    stat: int
    stat_string: str
    torrent_size: int
    total_peers: int
    pending_peers: int
    active_peers: int
    connected_seeders: int
    bytes_written: int
    bytes_read: int
    file_stats: list[TorrserverFileStat]

class TorrserverTorrentResponseBody(TypedDict):
    Hash: str
    Capacity: int
    Filled: int
    PiecesLength: int
    PiecesCount: int
    Torrent: TorrserverTorrent

def add_torrent(magnet_link) -> str:
    """
    Add a torrent to the client
    :param magnet_link: magnet link
    :return: identifier of the torrent
    """
    url = torrserver_url + "/torrents"
    headers = {
        "accept": "application/json, text/plain, */*",
        "content-type": "application/json",
    }
    data = {
        "action": "add",
        "link": magnet_link,
        "title": "",
        "poster": "",
        "save_to_db": False
    }
    response = requests.post(url, headers=headers, json=data)
    json_str = response.text

    # Convert the response text to a Python dictionary
    data = json.loads(json_str)

    return data['hash']


def torrserver_get_info(id: str) -> TorrserverTorrentResponseBody:
    url = torrserver_url + "/cache"
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
    }
    data = {
        "action": "get",
        "hash": id
    }
    response = requests.post(url, headers=headers, json=data)
    data = json.loads(response.text)
    return data


def torrserver_get_file(id: str, file_num: int) -> BytesIO:
    # http://localhost:8090/play/<hash_id>/<file_id>

    url = torrserver_get_file_download_link(file_num, id)

    download_response = requests.get(url, stream=True)
    download_response.raise_for_status()  # Ensure we got a successful response

    return io.BytesIO(download_response.content)

def torrserver_get_file_download_link(hash, file_id) -> str:
    def fix_filename(filename: str) -> str:
        """Fix the filename by replacing spaces, dots, and underscores with a dash and removing all other non-alphanumeric characters."""
        # Split to file name and extension
        filename, ext = os.path.splitext(filename)
        return ''.join(c if c.isalnum() else '-' if c in ' ._' else '' for c in filename) + ext

    info = torrserver_get_info(hash)
    download_file = next(filter(lambda f: f['id'] == int(file_id), info['Torrent']['file_stats']), None)
    download_file_name = fix_filename(os.path.basename(download_file['path'])) if download_file else file_id

    return f"{torrserver_url}/stream/{download_file_name}?link={hash}&index={file_id}&play"



