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
    release_data = discogs_request(f'releases/{release_id}')
    
    # Enhanced metadata processing for better YouTube search
    if release_data:
        # Clean and normalize artist names for better search
        if 'artists' in release_data:
            # Get primary artist name, handling various formats
            artists = release_data['artists']
            if artists:
                primary_artist = artists[0].get('name', '')
                # Remove common suffixes that might interfere with search
                primary_artist = primary_artist.replace(' (2)', '').replace(' (3)', '').strip()
                release_data['primary_artist'] = primary_artist
        
        # Extract and clean catalog number for better matching
        if 'labels' in release_data and release_data['labels']:
            for label in release_data['labels']:
                if 'catno' in label and label['catno']:
                    # Clean catalog number (remove extra spaces, normalize format)
                    catalog = label['catno'].strip().upper()
                    # Store cleaned catalog number
                    label['catno_clean'] = catalog
        
        # Extract format information for better context
        if 'formats' in release_data:
            formats = release_data['formats']
            format_info = []
            for fmt in formats:
                if 'name' in fmt:
                    format_info.append(fmt['name'])
                if 'descriptions' in fmt:
                    format_info.extend(fmt['descriptions'])
            
            # Create a search-friendly format string
            release_data['format_string'] = ' '.join(format_info).lower()
            
            # Detect if it's vinyl/electronic format
            vinyl_indicators = ['vinyl', '12"', 'ep', 'single', 'maxi-single']
            release_data['is_vinyl'] = any(indicator in release_data['format_string'] for indicator in vinyl_indicators)
        
        # Enhanced genre/style processing for electronic music detection
        if 'genres' in release_data:
            genres = [g.lower() for g in release_data['genres']]
            electronic_genres = ['electronic', 'techno', 'house', 'ambient', 'drum & bass', 'dubstep', 'experimental']
            release_data['is_electronic'] = any(genre in electronic_genres for genre in genres)
        
        if 'styles' in release_data:
            styles = [s.lower() for s in release_data['styles']]
            electronic_styles = ['techno', 'house', 'minimal', 'ambient', 'deep house', 'tech house', 'progressive house']
            if not release_data.get('is_electronic'):
                release_data['is_electronic'] = any(style in electronic_styles for style in styles)
        
        # Process tracklist for better individual track searches
        if 'tracklist' in release_data:
            for track in release_data['tracklist']:
                if 'title' in track:
                    # Clean track title for better search
                    clean_title = track['title'].strip()
                    # Remove common prefixes/suffixes that might interfere
                    clean_title = clean_title.replace('(Original Mix)', '').replace('(Club Mix)', '').strip()
                    track['clean_title'] = clean_title
                    
                    # Detect remix information
                    if 'remix' in clean_title.lower():
                        track['is_remix'] = True
                        # Try to extract remixer name
                        import re
                        remix_match = re.search(r'\(([^)]+)\s+remix\)', clean_title, re.IGNORECASE)
                        if remix_match:
                            track['remixer'] = remix_match.group(1).strip()
    
    return release_data 