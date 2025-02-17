import json
import os
from dataclasses import dataclass
from io import BytesIO
from typing import TypedDict

import dotenv
import requests

from src.utils import download, fix_filename

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

@dataclass
class DownloadLinkInfo:
    link: str
    file_name: str
    size_bytes: int
    torrent_name: str

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


def torrserver_get_info(hash: str) -> TorrserverTorrentResponseBody:
    url = torrserver_url + "/cache"
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
    }
    data = {
        "action": "get",
        "hash": hash
    }
    response = requests.post(url, headers=headers, json=data)
    data = json.loads(response.text)
    return data

def torrserver_get_file(hash: str, file_num: int) -> BytesIO:
    # http://localhost:8090/play/<hash_id>/<file_id>
    link = torrserver_get_file_download_link(hash, file_num).link
    return download(link)

def torrserver_get_file_download_link(hash, file_id) -> DownloadLinkInfo:
    info = torrserver_get_info(hash)['Torrent']
    download_file = next(filter(lambda f: f['id'] == int(file_id), info['file_stats']), None)
    if not download_file:
        raise ValueError(f"File with id {file_id} not found in the torrent. Can't get download link.")

    download_file_name = fix_filename(os.path.basename(download_file['path']))
    size_bytes = download_file['length']
    link = f"{torrserver_url}/stream/{download_file_name}?link={hash}&index={file_id}&play"

    return DownloadLinkInfo(link=link, file_name=download_file_name, torrent_name=info['title'], size_bytes=size_bytes)



