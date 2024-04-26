import io
import json
import os
from io import BytesIO

import dotenv
import requests

dotenv.load_dotenv()

torrserver_url = os.getenv("TORRSERVER_URL")

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


def get_info(id: str) -> dict:
    url = torrserver_url + "/cache"
    headers = {
        "accept": "application/json, text/plain, */*",
        "content-type": "application/json",
    }
    data = {
        "action": "get",
        "hash": id
    }
    response = requests.post(url, headers=headers, json=data)
    data = json.loads(response.text)
    return data


def get_file(id: str, file_num: int) -> BytesIO:
    # http://localhost:8090/play/<hash_id>/<file_id>

    url = get_file_download_link(file_num, id)

    download_response = requests.get(url, stream=True)
    download_response.raise_for_status()  # Ensure we got a successful response

    return io.BytesIO(download_response.content)


def get_file_download_link(hash, file_id) -> str:
    return f"{torrserver_url}/play/{hash}/{file_id}"
