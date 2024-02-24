import base64
import hashlib
import os
import urllib

import bencodepy
import dotenv
import requests
from requests.exceptions import InvalidSchema

dotenv.load_dotenv()

QBITTORRENT_URL = os.getenv('QBITTORRENT_URL')
QBITTORRENT_LOGIN = os.getenv('QBITTORRENT_LOGIN')
QBITTORRENT_PASSWORD = os.getenv('QBITTORRENT_PASSWORD')


def add_torrent_to_qbittorrent(torrent_link, name, tag='default') -> bool:
    # Login to qBittorrent Web UI
    session = login()

    if session is None:
        print('Failed to login to qBittorrent')

    add_url = f'{QBITTORRENT_URL}/api/v2/torrents/add'
    files = None

    params = {
        'rename': name,
        'tags': tag,
        'sequentialDownload': "true",
        'firstLastPiecePrio': "true",
        "skip_checking": "true",
        "ratioLimit": "1",
        "seedingTimeLimit": "1440",
    }

    if torrent_link.startswith('magnet:'):
        params['urls'] = torrent_link
    else:
        torrent_file = requests.get(torrent_link)
        files = {'torrents': ('torrent_file.torrent', torrent_file.content)}

    # Add torrent to qBittorrent
    response = session.post(add_url, data=params, files=files)

    logout(session)

    if response.ok:
        return True
    else:
        return False


def login():
    session = requests.Session()
    login_url = f'{QBITTORRENT_URL}/api/v2/auth/login'
    login_data = {'username': QBITTORRENT_LOGIN, 'password': QBITTORRENT_PASSWORD}
    response = session.post(login_url, data=login_data)

    if response.ok:
        return session
    else:
        return None


def logout(session):
    try:
        # Logout is not strictly necessary as the session will expire, but it's good practice
        logout_url = f'{QBITTORRENT_URL}/api/v2/auth/logout'
        session.get(logout_url)
    except:
        pass


def create_magnet_link_from_url(torrent_file_url) -> (str, bool, str):
    """
    Create a magnet link from a torrent file URL
    :return: tuple of magnet link, bool representing was it converted from torrent file
    (True if magnet was created from torrent file), torrent file bytes
    """
    if not torrent_file_url:
        return "", False, ""

    response = requests.get(torrent_file_url, allow_redirects=False)

    # If redirect get the new location
    if response.status_code == 302:
        location = response.headers['Location']
        # Go to it if it's not already a magnet link
        if not location.startswith('magnet:'):
            response = requests.get(location, allow_redirects=False)
        else:
            return location, False, ""

    if response.status_code != 200:
        return "Error downloading torrent file"

    torrent_data = response.content

    # Decode the torrent file
    try:
        torrent = bencodepy.decode(torrent_data)
    except Exception as e:
        return f"Error decoding torrent: {e}"

    # Extract the info dictionary and calculate the info hash
    info_hash = hashlib.sha1(bencodepy.encode(torrent[b'info'])).digest()

    # Convert the info hash to a hexadecimal string
    info_hash_hex = info_hash.hex()

    # Create the magnet link
    magnet_link = f"magnet:?xt=urn:btih:{info_hash_hex}"

    # Add the display name (dn) to the magnet link (optional)
    if b'name' in torrent[b'info']:
        display_name = torrent[b'info'][b'name'].decode('utf-8')
        # Properly URL-encode the display name
        encoded_display_name = urllib.parse.quote_plus(display_name)
        magnet_link += f"&dn={encoded_display_name}"

    # Return the magnet link
    return magnet_link, True, torrent_data


# Main
if __name__ == '__main__':
    # Test
    print(create_magnet_link_from_url('https://releases.ubuntu.com/23.10/ubuntu-23.10-live-server-amd64.iso.torrent'))
