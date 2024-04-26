import hashlib
import urllib
from pprint import pprint

import bencodepy
import dotenv
import requests

from torrserver import add_torrent, get_info, get_file

dotenv.load_dotenv()


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
    id_hash = add_torrent(
     #   "magnet:?xt=urn:btih:15AAE9E49CC516C0F113F702B410BEAA42B2BCEB&tr=http%3A%2F%2Fbt4.t-ru.org%2Fann%3Fmagnet"
    #   "magnet:?xt=urn:btih:3648baf850d5930510c1f172b534200ebb5496e6&dn=Ubuntu+24.04"
       "magnet:?xt=urn:btih:AF86870A619EFB3EBB0887F48CB2261A3A2A6809&tr=http%3A%2F%2Fbt3.t-ru.org%2Fann%3Fmagnet"
    )
    print("Add torrent result: ")
    pprint(id_hash)

    info = get_info(id_hash)
    print("Get info result: ")
    pprint(info)

    link = get_file(id_hash, 2)
    print("Get first file link result: ")
    pprint(link)

# http://localhost:8090/stream/?link=15aae9e49cc516c0f113f702b410beaa42b2bceb&index=1&play