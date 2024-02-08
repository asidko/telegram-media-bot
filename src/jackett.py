import os
import string
from random import random, choice

import dotenv
import humanize
import requests
from cachetools import cached, TTLCache
from cachetools_ext.fs import FSLRUCache
import hashlib

dotenv.load_dotenv()

JACKETT_SERVER_URL = os.getenv('JACKETT_SERVER_URL')
JACKETT_API_KEY = os.getenv('JACKETT_API_KEY')

cache = FSLRUCache(maxsize=50, ttl=900)  # cahce for 15 minutes (900 seconds)


@cached(cache, key=lambda query: hashlib.md5(query.encode()).hexdigest())
def search_jackett(query):
    print("Jackett: Searching for:", query)
    # Construct the URL for the search API
    search_url = f"{JACKETT_SERVER_URL}/api/v2.0/indexers/all/results?apikey={JACKETT_API_KEY}&Query={query}"

    # Make the request to the Jackett API
    response = requests.get(search_url)

    # Initialize an empty list to hold the parsed results
    parsed_results = []

    print("Jackett: Query: %s, Status: %s" % (query, response.status_code))

    # Check if the request was successful
    if response.status_code == 200:
        # Parse the JSON response
        results = response.json()

        # Iterate through the results and extract the desired information
        for result in results.get('Results', []):
            # Extracting the required fields from each result
            size = result.get('Size')
            # Convert size to human-readable format
            human_readable_size = humanize.naturalsize(size, format='%.2f', binary=False)
            # Generate UUID
            id = ''.join(choice(string.ascii_uppercase + string.digits) for _ in range(6))
            parsed_result = {
                'id': id,
                'title': result.get('Title'),
                'size_bytes': size,  # Size in bytes
                'size': human_readable_size,  # Size in bytes
                'seeds': result.get('Seeders'),
                'magnet': result.get('MagnetUri'),
                'torrent': result.get('Link'),
                'tracker': result.get('Tracker')
            }
            if parsed_result['torrent'] and parsed_result['torrent'].startswith('magnet:'):
                parsed_result['torrent'] = None
                parsed_results['magnet'] = result.get('Link')

            parsed_results.append(parsed_result)

        # Sort by seeds
        parsed_results = sorted(parsed_results, key=lambda x: x['seeds'], reverse=True)

        return parsed_results
    else:
        return f"Error: Received status code {response.status_code}"
