from dataclasses import dataclass, field
from time import sleep
from typing import Callable

from utils import bytes_to_human_readable
from torrserver import add_torrent, get_info
import threading


@dataclass
class TorrentFileInfo:
    id: str
    title: str
    size: str


@dataclass
class TorrentInfo:
    hash: str
    title: str
    size: str
    files: list[TorrentFileInfo] = field(default_factory=list)


def get_torrent_info_by_magnet_link(magnet_link,
                                    callback: Callable[[TorrentInfo | None], None],
                                    fail_callback: Callable[[],None] | None = None) -> None:
    def worker():
        attempt = 0
        tor_info = None
        id_hash = add_torrent(magnet_link)
        max_attempts = 15
        while attempt < max_attempts:
            attempt += 1
            print("Waiting for torrent info... Attempt %d" % attempt)
            _tor_info = get_info(id_hash)
            # Got some data
            if _tor_info is not None and _tor_info.get('Torrent') is not None:
                tor_info = _tor_info['Torrent']
                break
            sleep(1)

        if tor_info is None:
            print("Failed to get torrent info")
            if fail_callback:
                fail_callback()
            return

        torrent_info = TorrentInfo(
            hash=id_hash,
            title=tor_info.get('title'),
            size=bytes_to_human_readable(tor_info.get('torrent_size'))
        )
        for file in sorted(tor_info['file_stats'], key=lambda x: x['length'], reverse=True):
            torrent_info.files.append(TorrentFileInfo(
                id=file.get('id'),
                title=file.get('path'),
                size=bytes_to_human_readable(file.get('length'))
            ))
        callback(torrent_info)

    thread = threading.Thread(target=worker)
    thread.start()


