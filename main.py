import requests
import json
import logging
import time
from urllib.parse import urlencode
from bs4 import BeautifulSoup

from clean_item import clean_item

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
BASE_URL = "https://www.mixesdb.com/w/MixesDB:Explorer/Mixes"

# Request configuration
REQUEST_TIMEOUT = 20  # Increased from 10 to 20 seconds
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds between retries


def build_url(artist_name, offset, other_params):
    """Build the URL for the MixesDB request."""
    params = {
        "do": "mx",
        "mode": "",
        "cat1": artist_name,
        "cat2": "",
        "jnC": "",
        "style": "",
        "year": "",
        "tlC": "1",
        "tlI": "1",
        "so": "",
        "tmatch1": "",
        "tmatch2": "",
        "jnTm": "",
        "usesFile": "",
        "minHotnessLevel": "",
        "count": "25",
        "order": "name",
        "sort": "desc",
        "offset": str(offset),
        **other_params
    }
    query_string = urlencode(params)
    return f"{BASE_URL}?{query_string}"


def fetch_with_retry(url, max_retries=MAX_RETRIES, retry_delay=RETRY_DELAY):
    """Fetch URL with retry logic."""
    for attempt in range(max_retries):
        try:
            logger.info(f"Request attempt {attempt + 1} for: {url}")
            response = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            logger.warning(f"Attempt {attempt + 1} failed: {str(e)}")
            if attempt < max_retries - 1:
                logger.info(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                logger.error(f"All {max_retries} attempts failed for URL: {url}")
                raise


def fetch_tracklists(artist_name, offset, other_params):
    """Fetch tracklists from MixesDB."""
    url = build_url(artist_name, offset, other_params)
    logger.info(f"Fetching URL: {url}")
    
    try:
        response = fetch_with_retry(url)
        return BeautifulSoup(response.content, "html.parser")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching tracklists: {str(e)}")
        raise ValueError(f"Failed to fetch data from MixesDB: {str(e)}")


def parse_tracklists(soup):
    """Parse the tracklists from the BeautifulSoup object."""
    tracklists = []
    
    # Find all explorer result sections
    explorer_results = soup.find_all("div", class_="explorerResult")
    logger.info(f"Found {len(explorer_results)} explorer results")
    
    for explorerResult in explorer_results:
        tracklist = []
        ol_tags = explorerResult.find_all("ol")
        
        for ol_tag in ol_tags:
            li_tags = ol_tag.find_all("li")
            for li_tag in li_tags:
                track_name = li_tag.text.strip()
                track_id = clean_item(track_name)
                tracklist.append({"track": track_name, "id": track_id})
        
        if tracklist:
            tracklists.append(tracklist)
    
    return tracklists


def write_to_json(tracklists, filename="tracklists.json"):
    """Write tracklists to a JSON file."""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(tracklists, f, ensure_ascii=False, indent=4)
        logger.info(f"Successfully wrote tracklists to {filename}")
    except Exception as e:
        logger.error(f"Error writing to JSON file: {str(e)}")


def get_total_track_lists(artist_name):
    """Get the total number of tracklists for an artist."""
    url = build_url(artist_name, 0, {})
    
    try:
        logger.info(f"Fetching total number of tracks for {artist_name}")
        page = fetch_with_retry(url)
        
        soup = BeautifulSoup(page.content, "html.parser")
        
        # Get total number of track lists
        explorer_res_class = soup.find("span", class_="explorerRes")
        if not explorer_res_class:
            logger.warning("Could not find explorerRes class in the response")
            return 0
            
        b_tag = explorer_res_class.find("b")
        if not b_tag:
            logger.warning("Could not find b tag in explorerRes class")
            return 0
            
        total = b_tag.text.strip()
        logger.info(f"Total track lists for {artist_name}: {total}")
        return int(total)
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error getting total tracklists: {str(e)}")
        raise ValueError(f"Failed to get total track lists: {str(e)}")
    except ValueError as e:
        logger.error(f"Value error parsing total: {str(e)}")
        return 0
    except Exception as e:
        logger.error(f"Unexpected error getting total tracklists: {str(e)}")
        return 0


def main(artist_name):
    """Main function to fetch and process tracklists."""
    if not artist_name:
        raise ValueError("Artist name is required")
        
    logger.info(f"Processing artist: {artist_name}")
    
    try:
        # Get total number of track lists
        total_track_lists = get_total_track_lists(artist_name)
        
        if total_track_lists == 0:
            logger.warning(f"No tracklists found for {artist_name}")
            return []
            
        all_tracklists = []
        logger.info(f"Fetching {total_track_lists} tracklists in batches of 25")
        
        # Limit to a reasonable number to prevent extremely long processing times
        max_to_fetch = min(total_track_lists, 100)
        
        for offset in range(0, max_to_fetch, 25):
            logger.info(f"Fetching batch starting at offset {offset}")
            soup = fetch_tracklists(artist_name, offset, {})
            tracklists = parse_tracklists(soup)
            all_tracklists.extend(tracklists)
            
        flat_tracklist = [track for sublist in all_tracklists for track in sublist]
        logger.info(f"Successfully processed {len(flat_tracklist)} tracks for {artist_name}")
        
        # Optionally save to file
        # write_to_json(flat_tracklist)
        
        return flat_tracklist
        
    except Exception as e:
        logger.error(f"Error in main function for {artist_name}: {str(e)}")
        raise


if __name__ == "__main__":
    try:
        artist = input("Enter artist name: ")
        tracklist = main(artist)
        print(f"Found {len(tracklist)} tracks for {artist}")
    except Exception as e:
        print(f"Error: {str(e)}")
