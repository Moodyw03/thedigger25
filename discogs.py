import requests
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_discogs_token():
    token = os.getenv('DISCOGS_TOKEN')
    if not token:
        logger.warning("DISCOGS_TOKEN not found in environment variables")
    return token

def get_discogs_user_agent():
    user_agent = os.getenv('DISCOGS_USER_AGENT', 'TheDigger/1.0 +@https://github.com/Moodyw03/thedigger25')
    return user_agent

def discogs_request(endpoint, params=None):
    """Make a request to the Discogs API with proper authentication"""
    token = get_discogs_token()
    user_agent = get_discogs_user_agent()
    
    if not token:
        raise ValueError("Discogs API token not configured. Please set DISCOGS_TOKEN in your environment.")
    
    headers = {
        'Authorization': f'Discogs token={token}',
        'User-Agent': user_agent
    }
    
    url = f'https://api.discogs.com/{endpoint}'
    
    try:
        logger.info(f"Making Discogs API request to: {url}")
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Discogs API request failed: {str(e)}")
        raise

def search_labels(query, page=1, per_page=10):
    """Search for labels matching the query"""
    params = {
        'q': query,
        'type': 'label',
        'page': page,
        'per_page': per_page
    }
    return discogs_request('database/search', params)

def get_label_releases(label_id, page=1, per_page=100, sort='year', sort_order='desc'):
    """Get releases for a specific label"""
    params = {
        'page': page,
        'per_page': per_page,
        'sort': sort,
        'sort_order': sort_order
    }
    return discogs_request(f'labels/{label_id}/releases', params)

def get_release_details(release_id):
    """Get detailed information about a specific release"""
    return discogs_request(f'releases/{release_id}') 