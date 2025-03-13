import requests
import json
import logging
import time
from urllib.parse import urlencode, quote
from bs4 import BeautifulSoup
import re
import os
import random
from datetime import datetime

from clean_item import clean_item

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Request configuration
REQUEST_TIMEOUT = int(os.environ.get("REQUEST_TIMEOUT", 20))  # Timeout in seconds
MAX_RETRIES = int(os.environ.get("MAX_RETRIES", 3))  # Number of retry attempts
RETRY_DELAY = int(os.environ.get("RETRY_DELAY", 2))  # Seconds between retries
# Default maximum number of pages to fetch 
MAX_FETCH_LIMIT = int(os.environ.get("MAX_FETCH_LIMIT", 300))
# Default maximum number of pagination pages to fetch
MAX_PAGINATION_PAGES = int(os.environ.get("MAX_PAGINATION_PAGES", 10))
# Rate limiting - requests per minute
RATE_LIMIT_RPM = int(os.environ.get("RATE_LIMIT_RPM", 30))
# Minimum delay between requests in seconds
MIN_REQUEST_DELAY = 60.0 / RATE_LIMIT_RPM  # Convert RPM to seconds

# Set up user agent from environment
USER_AGENT = os.environ.get("YOUTUBE_USER_AGENT", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
HEADERS = {"User-Agent": USER_AGENT}

# Simple request cache to reduce network calls
request_cache = {}
CACHE_EXPIRY = int(os.environ.get('CACHE_EXPIRY', 86400))  # 24 hours in seconds
last_request_time = 0  # Track the time of the last request for rate limiting

# Base URL for the Explorer endpoint
EXPLORER_BASE_URL = "https://www.mixesdb.com/w/MixesDB:Explorer/Mixes"
# Base URL for the Category pages
CATEGORY_BASE_URL = "https://www.mixesdb.com/w/Category:"


def build_explorer_url(artist_name, offset, other_params):
    """Build the URL for the MixesDB Explorer request."""
    params = {
        "do": "mx",
        "mode": "",
        "cat1": artist_name,
        "cat2": "",
        "jnC": "",
        "style": "",
        "year": "",
        "tlC": "",
        "tlI": "",
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
    }
    
    # Update with any additional parameters
    if other_params:
        params.update(other_params)
    
    query_string = urlencode(params)
    return f"{EXPLORER_BASE_URL}?{query_string}"


def build_category_url(artist_name):
    """Build the URL for the MixesDB Category page."""
    # For specific artists with known URL formats, use the correct format
    if artist_name.lower() == "ben ufo":
        return f"{CATEGORY_BASE_URL}Ben_UFO"
    
    # Try both underscore and hyphen versions for artists with spaces
    if " " in artist_name:
        # Replace spaces with underscores and handle special characters
        formatted_name = artist_name.replace(' ', '_')
        # URL encode the artist name
        encoded_name = quote(formatted_name)
        return f"{CATEGORY_BASE_URL}{encoded_name}"
    else:
        # If no spaces, just encode the name
        encoded_name = quote(artist_name)
        return f"{CATEGORY_BASE_URL}{encoded_name}"


def enforce_rate_limit():
    """Enforce rate limiting by waiting appropriate amount of time between requests."""
    global last_request_time
    current_time = time.time()
    time_since_last_request = current_time - last_request_time
    
    if time_since_last_request < MIN_REQUEST_DELAY:
        wait_time = MIN_REQUEST_DELAY - time_since_last_request
        logger.debug(f"Rate limiting: Waiting {wait_time:.2f} seconds before next request")
        time.sleep(wait_time)
    
    last_request_time = time.time()


def manage_cache():
    """Clean up expired cache entries to prevent memory bloat."""
    global request_cache
    
    current_time = time.time()
    expired_keys = [url for url, (cache_time, _) in request_cache.items() 
                   if current_time - cache_time > CACHE_EXPIRY]
    
    for url in expired_keys:
        del request_cache[url]
    
    if expired_keys:
        logger.info(f"Cache management: Removed {len(expired_keys)} expired entries. Cache now has {len(request_cache)} entries.")


def categorize_error(error):
    """Categorize error as transient or permanent to inform retry strategy."""
    if isinstance(error, requests.exceptions.Timeout):
        return "timeout", True  # Transient
    elif isinstance(error, requests.exceptions.ConnectionError):
        return "connection", True  # Transient
    elif isinstance(error, requests.exceptions.HTTPError):
        # 5xx errors are server errors, likely transient
        if hasattr(error, 'response') and error.response.status_code >= 500:
            return f"server_error_{error.response.status_code}", True
        # 4xx errors are client errors, likely permanent
        elif hasattr(error, 'response') and error.response.status_code >= 400:
            return f"client_error_{error.response.status_code}", False
        else:
            return "http_error", True  # Assume most HTTP errors are transient
    else:
        return "unknown", True  # Default to treating unknown errors as transient


def fetch_with_retry(url, max_retries=MAX_RETRIES, retry_delay=RETRY_DELAY):
    """Fetch URL with retry logic and caching."""
    # Manage cache periodically
    if random.random() < 0.05:  # 5% chance to run cache management
        manage_cache()
    
    # Check if the URL is in the cache and not expired
    if url in request_cache:
        cache_time, cached_response = request_cache[url]
        if time.time() - cache_time < CACHE_EXPIRY:
            logger.info(f"Using cached response for: {url}")
            return cached_response
    
    # Enforce rate limiting before making the request
    enforce_rate_limit()
    
    transient_errors = 0
    permanent_errors = 0
    
    for attempt in range(max_retries):
        try:
            logger.info(f"Request attempt {attempt + 1} for: {url}")
            response = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            
            # Store successful response in cache
            request_cache[url] = (time.time(), response)
            
            return response
        except requests.exceptions.RequestException as e:
            error_type, is_transient = categorize_error(e)
            
            if is_transient:
                transient_errors += 1
                logger.warning(f"Transient error ({error_type}) in attempt {attempt + 1}: {str(e)}")
                
                if attempt < max_retries - 1:
                    # Progressive backoff with jitter for transient errors
                    backoff_factor = min(2 ** attempt, 60)  # Cap to 60 seconds
                    jitter = random.uniform(0, 1)
                    sleep_time = retry_delay * backoff_factor + jitter
                    
                    logger.info(f"Retrying in {sleep_time:.2f} seconds...")
                    time.sleep(sleep_time)
                else:
                    logger.error(f"All {max_retries} attempts failed for URL: {url} (transient errors: {transient_errors})")
                    raise
            else:
                permanent_errors += 1
                logger.error(f"Permanent error ({error_type}) encountered: {str(e)}")
                # No point retrying permanent errors
                raise


def fetch_tracklists_explorer(artist_name, offset, other_params):
    """Fetch tracklists from MixesDB Explorer page."""
    url = build_explorer_url(artist_name, offset, other_params)
    logger.info(f"Fetching Explorer URL: {url}")
    
    try:
        response = fetch_with_retry(url)
        return BeautifulSoup(response.content, "html.parser")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching Explorer tracklists: {str(e)}")
        raise ValueError(f"Failed to fetch data from MixesDB Explorer: {str(e)}")


def fetch_tracklists_category(artist_name):
    """Fetch tracklists from MixesDB Category page."""
    url = build_category_url(artist_name)
    logger.info(f"Fetching Category URL: {url}")
    
    try:
        response = fetch_with_retry(url)
        return BeautifulSoup(response.content, "html.parser")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching Category tracklists: {str(e)}")
        raise ValueError(f"Failed to fetch data from MixesDB Category: {str(e)}")


def fetch_all_category_pages(artist_name, max_pages=MAX_PAGINATION_PAGES):
    """Fetch all pages for a category, handling pagination, with a configurable limit."""
    url = build_category_url(artist_name)
    logger.info(f"Fetching first category page: {url}")
    
    all_pages = []
    visited_urls = set()  # Keep track of URLs we've already visited to avoid loops
    
    try:
        # Fetch first page
        response = fetch_with_retry(url)
        soup = BeautifulSoup(response.content, "html.parser")
        all_pages.append(soup)
        visited_urls.add(url)
        
        # Check for pagination links - MixesDB uses specific navigation at the bottom
        page_count = 1
        
        # Special case for Ben UFO - directly handle the pagefrom URL we know exists
        if artist_name.lower() == "ben ufo":
            # First try the pagefrom URL we know exists for Ben UFO
            ben_ufo_second_page = f"https://www.mixesdb.com/w/index.php?title=Category:Ben_UFO&pagefrom=2017-06-22+-+Ben+UFO%2C+Batu+-+Hessle+Audio%2C+Rinse+FM#mw-pages"
            if ben_ufo_second_page not in visited_urls:
                logger.info(f"Fetching known second page for Ben UFO: {ben_ufo_second_page}")
                response = fetch_with_retry(ben_ufo_second_page)
                soup = BeautifulSoup(response.content, "html.parser")
                all_pages.append(soup)
                visited_urls.add(ben_ufo_second_page)
                page_count += 1
                logger.info(f"Fetched Ben UFO category page {page_count}")
        
        # Look for pagination in different possible locations
        
        # Try to find pagination links in various formats
        pagination_found = True
        current_soup = soup
        
        while pagination_found and page_count < max_pages:
            pagination_found = False
            
            # Progress indicator
            logger.info(f"Pagination progress: {page_count}/{max_pages} pages fetched")
            
            # 1. Check for standard MediaWiki pagination navigation
            nav_div = current_soup.find('div', class_='mw-allpages-nav')
            
            # 2. Check for category specific pagination 
            if not nav_div:
                nav_div = current_soup.find('div', id='mw-pages')
            
            # 3. Look for direct listPagination divs
            if not nav_div:
                nav_div = current_soup.find('div', class_='listPagination')
            
            # 4. Check for any text with "next" in it
            if nav_div:
                # First look for "next" links
                pagination = nav_div.find('a', text=re.compile('next', re.IGNORECASE))
                
                # If no "next" link found, look for "pagefrom" in URLs
                if not pagination:
                    for link in nav_div.find_all('a'):
                        href = link.get('href', '')
                        if ('pagefrom=' in href or 'pageuntil=' in href) and href not in visited_urls:
                            pagination = link
                            break
                
                # If we found a pagination link, follow it
                if pagination:
                    next_url = pagination.get('href')
                    if not next_url.startswith('http'):
                        next_url = f"https://www.mixesdb.com{next_url}"
                    
                    # Skip if we've already visited this URL
                    if next_url in visited_urls:
                        break
                    
                    logger.info(f"Fetching next category page: {next_url}")
                    try:
                        response = fetch_with_retry(next_url)
                        current_soup = BeautifulSoup(response.content, "html.parser")
                        all_pages.append(current_soup)
                        visited_urls.add(next_url)
                        
                        page_count += 1
                        logger.info(f"Fetched category page {page_count}")
                        pagination_found = True
                    except Exception as e:
                        error_type, is_transient = categorize_error(e) if hasattr(e, 'response') else ("unknown", True)
                        logger.error(f"Error fetching next page {next_url}: {str(e)} (Error type: {error_type}, Transient: {is_transient})")
                        if not is_transient:
                            # If it's a permanent error, stop trying
                            break
                        else:
                            # For transient errors, we can try alternative methods
                            pass
            
            # If we don't have navigation div but there might be more paginations:
            # Try to extract "next 200" links from any location in the document
            if not pagination_found:
                for link in current_soup.find_all('a'):
                    link_text = link.get_text().strip().lower()
                    href = link.get('href', '')
                    
                    # Check for next page indicators
                    if (('next' in link_text and ('200' in link_text or '100' in link_text)) or
                        'pagefrom=' in href or 'pageuntil=' in href) and href not in visited_urls:
                        
                        next_url = link.get('href')
                        if not next_url.startswith('http'):
                            next_url = f"https://www.mixesdb.com{next_url}"
                        
                        if next_url in visited_urls:
                            continue
                        
                        logger.info(f"Fetching next category page (secondary method): {next_url}")
                        try:
                            response = fetch_with_retry(next_url) 
                            current_soup = BeautifulSoup(response.content, "html.parser")
                            all_pages.append(current_soup)
                            visited_urls.add(next_url)
                            
                            page_count += 1
                            logger.info(f"Fetched category page {page_count}")
                            pagination_found = True
                            break
                        except Exception as e:
                            error_type, is_transient = categorize_error(e) if hasattr(e, 'response') else ("unknown", True)
                            logger.error(f"Error fetching next page {next_url}: {str(e)} (Error type: {error_type}, Transient: {is_transient})")
        
        if page_count >= max_pages:
            logger.info(f"Reached configured maximum of {max_pages} pages, stopping pagination fetch")
        else:
            logger.info(f"Fetched all available category pages ({page_count} total)")
        
        return all_pages
        
    except requests.exceptions.RequestException as e:
        error_type, is_transient = categorize_error(e) if hasattr(e, 'response') else ("unknown", True)
        logger.error(f"Error fetching category pages: {str(e)} (Error type: {error_type}, Transient: {is_transient})")
        raise


def parse_tracklists_explorer(soup):
    """Parse the tracklists from the Explorer page BeautifulSoup object."""
    tracklists = []
    
    # Find all explorer result sections
    explorer_results = soup.find_all("div", class_="explorerResult")
    logger.info(f"Found {len(explorer_results)} explorer results")
    
    for explorerResult in explorer_results:
        # Extract mix title and date
        mix_info = {}
        title_element = explorerResult.find("div", class_="explorerTitle")
        
        if title_element:
            # Find the mix title - it's usually in an <a> tag inside the title div
            title_link = title_element.find("a")
            if title_link:
                mix_info["title"] = title_link.text.strip()
                # Save the mix URL for potential future use
                mix_info["url"] = title_link.get("href", "")
                if mix_info["url"] and not mix_info["url"].startswith("http"):
                    mix_info["url"] = f"https://www.mixesdb.com{mix_info['url']}"
            
            # Try to find the date - it's usually in parentheses in the title div text
            date_text = title_element.text
            date_match = re.search(r'\(([^)]+)\)', date_text)
            if date_match:
                mix_info["date"] = date_match.group(1).strip()
            else:
                mix_info["date"] = "Unknown date"
        
        if not mix_info.get("title"):
            mix_info["title"] = "Untitled Mix"
            
        tracklist = []
        ol_tags = explorerResult.find_all("ol")
        
        for ol_tag in ol_tags:
            li_tags = ol_tag.find_all("li")
            for li_tag in li_tags:
                track_name = li_tag.text.strip()
                track_id = clean_item(track_name)
                tracklist.append({"track": track_name, "id": track_id})
        
        # Add mix info to the tracklist, even if the tracklist is empty
        tracklists.append({
            "title": mix_info.get("title", "Untitled Mix"),
            "date": mix_info.get("date", "Unknown date"),
            "url": mix_info.get("url", ""),
            "tracks": tracklist,
            "has_tracklist": len(tracklist) > 0
        })
    
    return tracklists


def parse_category_page(soup, artist_name):
    """Parse the Category page to find all mixes and their details."""
    tracklists = []
    
    # The content area typically has the mixes listed
    content_div = soup.find("div", id="mw-content-text")
    if not content_div:
        logger.warning(f"Could not find content div on category page for {artist_name}")
        return tracklists
    
    # Find all unordered lists that might contain mixes
    ul_tags = content_div.find_all("ul")
    
    # Track if we found any mixes
    found_mixes = False
    
    for ul_tag in ul_tags:
        # Find all list items
        li_tags = ul_tag.find_all("li")
        for li_tag in li_tags:
            # Each list item typically contains a link to a mix
            link = li_tag.find("a")
            if not link:
                continue
                
            mix_title = link.text.strip()
            mix_url = link.get("href", "")
            if mix_url and not mix_url.startswith("http"):
                mix_url = f"https://www.mixesdb.com{mix_url}"
            
            # Try to find the date in the text or list item content
            date = "Unknown date"
            date_match = re.search(r'\((\d{1,2}(?:st|nd|rd|th)? [A-Za-z]+,? \d{4})\)', li_tag.text)
            if date_match:
                date = date_match.group(1).strip()
            else:
                # Try another date format
                date_match = re.search(r'\((\d{4}-\d{2}-\d{2})\)', li_tag.text)
                if date_match:
                    date = date_match.group(1).strip()
            
            # We'll need to fetch the individual mix page to get the tracklist
            try:
                tracklist = fetch_mix_tracklist(mix_url)
                found_mixes = True
                
                # Add the mix regardless of whether it has a tracklist or not
                tracklists.append({
                    "title": mix_title,
                    "date": date,
                    "url": mix_url,
                    "tracks": tracklist,
                    "has_tracklist": len(tracklist) > 0
                })
                
                if tracklist:
                    logger.info(f"Added mix: {mix_title} with {len(tracklist)} tracks")
                else:
                    logger.info(f"Added mix: {mix_title} (no tracklist available)")
                
            except Exception as e:
                logger.warning(f"Error fetching tracklist for mix {mix_title}: {str(e)}")
                # Still add the mix even if there was an error fetching the tracklist
                tracklists.append({
                    "title": mix_title,
                    "date": date,
                    "url": mix_url,
                    "tracks": [],
                    "has_tracklist": False
                })
                logger.info(f"Added mix: {mix_title} (error fetching tracklist)")
    
    if not found_mixes:
        logger.warning(f"No mixes found in category page for {artist_name}")
    
    return tracklists


def extract_tracklist_from_text(text):
    """Extract tracklist from raw text content by looking for patterns."""
    tracklist = []
    
    # Split text into lines
    lines = text.split('\n')
    
    # Keep track of consecutive track-like lines
    track_section = False
    track_count = 0
    
    # Common patterns for track listings:
    # 1. Timestamps (00:00, 1:23, etc.)
    # 2. Track numbers with period/dash/bracket ([01], 1., 1 -, etc.)
    # 3. Artist - Title format
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Check if line looks like a track
        is_track = False
        
        # Check for timestamp pattern
        if re.search(r'^\d+:\d+', line):
            is_track = True
        # Check for numbered track pattern
        elif re.search(r'^\[\d+\]|\d+\s*[.-]\s+|\d+\s*\)', line):
            is_track = True
        # Check for Resident Advisor pattern (number followed by dot and artist name)
        elif re.search(r'^\d+\.\s*[A-Za-z]', line):
            is_track = True
        # Check for artist - title pattern (only if it contains a dash with spaces)
        elif ' - ' in line and len(line) > 7:  # Minimum length to avoid false positives
            is_track = True
            
        if is_track:
            track_section = True
            track_count += 1
            track_id = clean_item(line)
            tracklist.append({"track": line, "id": track_id})
        else:
            # If we're in a track section and find text that's not a track,
            # check if it might be a continuation of a track
            if track_section and track_count > 0 and len(line) < 100:  # Reasonable length for a continuation
                # Add to the previous track if it's a continuation
                if tracklist:
                    prev_track = tracklist[-1]["track"]
                    tracklist[-1]["track"] = f"{prev_track} {line}"
                    tracklist[-1]["id"] = clean_item(tracklist[-1]["track"])
            else:
                # Reset track section if we encounter non-track text
                # Only reset if we've seen a minimum number of consecutive track-like lines
                if track_count < 2:
                    track_section = False
                    track_count = 0
                    tracklist = []  # Reset if we only found 1 isolated track-like line
                # Don't reset if we've already found multiple tracks
    
    # Only return tracklist if we found at least 2 tracks
    return tracklist if len(tracklist) >= 2 else []


def extract_tracklist_from_section(soup, section_title="Tracklist"):
    """Extract tracklist from a section with a specific heading."""
    tracklist = []
    
    # Find the section heading (commonly h2, h3, etc.)
    headings = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
    section_heading = None
    
    for heading in headings:
        if section_title.lower() in heading.text.strip().lower():
            section_heading = heading
            break
    
    # If we found the section heading, extract the tracklist
    if section_heading:
        logger.info(f"Found '{section_title}' section heading")
        # Find the tracks that follow the heading
        current_element = section_heading.next_sibling
        
        # Initialize a list to collect potential track elements
        track_elements = []
        
        # Look through subsequent elements until we hit another heading or run out of siblings
        while current_element and not (current_element.name and current_element.name.startswith('h')):
            # Add element to our collection if it might contain track information
            if current_element.name in ['ol', 'ul', 'p', 'div']:
                track_elements.append(current_element)
            current_element = current_element.next_sibling
        
        # First, look for ordered lists (most common for tracklists)
        for element in track_elements:
            if element.name == 'ol':
                li_tags = element.find_all('li')
                for li_tag in li_tags:
                    track_name = li_tag.text.strip()
                    if track_name and not track_name.startswith("?"):
                        track_id = clean_item(track_name)
                        tracklist.append({"track": track_name, "id": track_id})
                
                # If we found tracks in this list, we're done
                if tracklist:
                    logger.info(f"Extracted {len(tracklist)} tracks from ordered list after '{section_title}' heading")
                    return tracklist
        
        # If no ordered list with tracks, try unordered lists
        if not tracklist:
            for element in track_elements:
                if element.name == 'ul':
                    li_tags = element.find_all('li')
                    for li_tag in li_tags:
                        track_name = li_tag.text.strip()
                        if track_name and not track_name.startswith("?"):
                            track_id = clean_item(track_name)
                            tracklist.append({"track": track_name, "id": track_id})
                    
                    if tracklist:
                        logger.info(f"Extracted {len(tracklist)} tracks from unordered list after '{section_title}' heading")
                        return tracklist
        
        # If still no tracklist, try paragraphs and divs
        if not tracklist:
            # Combine text from all elements and check for track-like patterns
            combined_text = ""
            for element in track_elements:
                if element.name in ['p', 'div']:
                    combined_text += element.text.strip() + "\n"
            
            if combined_text:
                tracks_from_text = extract_tracklist_from_text(combined_text)
                if tracks_from_text:
                    logger.info(f"Extracted {len(tracks_from_text)} tracks from text content after '{section_title}' heading")
                    return tracks_from_text
    
    return tracklist


def extract_resident_advisor_tracklist(soup):
    """Extract tracklist specifically from Resident Advisor format pages."""
    tracklist = []
    
    # Look for a div containing the tracklist
    content_div = soup.find("div", id="mw-content-text")
    if not content_div:
        return tracklist
    
    # Find all paragraphs in the content area
    p_tags = content_div.find_all("p")
    
    # Check for Resident Advisor's tracklist format
    found_tracklist_header = False
    current_track_section = []
    
    for p in p_tags:
        text = p.text.strip()
        
        # Skip empty paragraphs
        if not text:
            continue
            
        # Look for "Tracklist" header
        if 'tracklist' in text.lower() and not found_tracklist_header:
            found_tracklist_header = True
            continue
            
        # If we found the tracklist header, start collecting tracks
        if found_tracklist_header:
            # Stop if we hit another section
            if re.match(r'^[A-Z][a-z]+:', text) and not re.match(r'^\d+\.', text):
                break
                
            # Process the paragraph as potential tracks
            # Resident Advisor typically has track listings in "1. Artist - Title" format
            if re.search(r'^\d+\.', text) or ' - ' in text:
                # This might be a list of tracks in a single paragraph
                lines = text.split('\n')
                for line in lines:
                    line = line.strip()
                    if line:
                        current_track_section.append(line)
    
    # Process tracks with numbers (e.g., "1. Artist - Track")
    numbered_pattern = re.compile(r'(\d+)\.\s*(.*)')
    
    # Process the collected track section
    for line in current_track_section:
        match = numbered_pattern.match(line)
        if match:
            # This is a numbered track
            track_name = match.group(2).strip()
            if track_name:
                track_id = clean_item(track_name)
                tracklist.append({"track": track_name, "id": track_id})
        elif ' - ' in line:
            # This might be an unnumbered "Artist - Title" format
            track_id = clean_item(line)
            tracklist.append({"track": line, "id": track_id})
    
    logger.info(f"Extracted {len(tracklist)} tracks from Resident Advisor format")
    return tracklist


def fetch_mix_tracklist(mix_url):
    """Fetch and parse the tracklist from an individual mix page."""
    logger.info(f"Fetching mix tracklist from: {mix_url}")
    tracklist = []
    
    try:
        response = fetch_with_retry(mix_url)
        soup = BeautifulSoup(response.content, "html.parser")
        
        # Special case for Ben UFO mixes
        if "Ben_UFO" in mix_url or "Ben-UFO" in mix_url:
            logger.info("Detected Ben UFO mix, using specialized extraction")
            # Try direct extraction of tracklist table - common in Ben UFO pages
            table_tracklist = []
            for table in soup.find_all("table", class_=lambda c: c and "wikitable" in c):
                for row in table.find_all("tr"):
                    cells = row.find_all("td")
                    if len(cells) >= 2:  # Typical [time, track] format
                        track_name = cells[1].text.strip()
                        if track_name and len(track_name) > 3:
                            track_id = clean_item(track_name)
                            table_tracklist.append({"track": track_name, "id": track_id})
            
            if table_tracklist:
                logger.info(f"Found {len(table_tracklist)} tracks in table format for Ben UFO mix")
                return table_tracklist
        
        # Special case for Resident Advisor mixes
        if "Resident_Advisor" in mix_url or "RA." in mix_url:
            logger.info("Detected Resident Advisor format, using specialized extraction")
            tracklist = extract_resident_advisor_tracklist(soup)
            if tracklist:
                return tracklist
        
        # First, try to extract tracklist from a section with "Tracklist" heading
        tracklist = extract_tracklist_from_section(soup, "Tracklist")
        if tracklist:
            logger.info(f"Successfully extracted {len(tracklist)} tracks from Tracklist section")
            return tracklist
            
        # Find the tracklist section - typically in a div with class "tracklist"
        tracklist_div = soup.find("div", class_="tracklist")
        if tracklist_div:
            # Find all list items in the tracklist
            ol_tags = tracklist_div.find_all("ol")
            for ol_tag in ol_tags:
                li_tags = ol_tag.find_all("li")
                for li_tag in li_tags:
                    track_name = li_tag.text.strip()
                    
                    # Skip empty tracks or tracks that are just symbols
                    if not track_name or track_name.strip() in ['?', '-', '–', '—', '•']:
                        continue
                        
                    track_id = clean_item(track_name)
                    tracklist.append({"track": track_name, "id": track_id})
            
            logger.info(f"Found {len(tracklist)} tracks in tracklist div")
        
        # If no tracks found in the tracklist div, try alternative methods
        if not tracklist:
            # Look for any "## Tracklist" or similar markdown-style headers
            for h_tag in soup.find_all(['h1', 'h2', 'h3', 'h4']):
                if 'tracklist' in h_tag.text.lower():
                    next_element = h_tag.find_next_sibling()
                    if next_element and next_element.name == 'ol':
                        for li in next_element.find_all('li'):
                            track_name = li.text.strip()
                            if track_name:
                                track_id = clean_item(track_name)
                                tracklist.append({"track": track_name, "id": track_id})
                        if tracklist:
                            logger.info(f"Found {len(tracklist)} tracks after header '{h_tag.text}'")
                            break
            
            # Direct table extraction for any mix page
            if not tracklist:
                for table in soup.find_all("table"):
                    track_rows = []
                    # Look for tables with a structure that might contain track listings
                    if table.find("th") and table.find("th").text.strip().lower() in ["track", "title", "artist", "time"]:
                        # This might be a track listing table
                        for row in table.find_all("tr"):
                            cells = row.find_all("td")
                            if len(cells) >= 2:  # At least 2 columns (typically track number/time and track name)
                                # Use the second column as it typically contains the track name
                                track_name = cells[1].text.strip()
                                if track_name and not track_name.startswith("?"):
                                    track_id = clean_item(track_name)
                                    track_rows.append({"track": track_name, "id": track_id})
                    
                    if track_rows:
                        tracklist.extend(track_rows)
                        logger.info(f"Found {len(track_rows)} tracks in a table")
                        break
            
            # Check for SoundCloud tracklist - often present near iframes or in paragraphs
            if not tracklist and soup.find("iframe", src=lambda x: x and "soundcloud.com" in x):
                iframe_soundcloud = soup.find("iframe", src=lambda x: x and "soundcloud.com" in x)
                logger.info("Found SoundCloud embed, looking for tracklist nearby")
                # Look for tracklist in paragraphs near the SoundCloud iframe
                parent = iframe_soundcloud.parent
                # Check paragraphs after the iframe
                next_elements = list(parent.next_siblings)
                for element in next_elements:
                    if element.name == 'p':
                        text_content = element.text.strip()
                        tracks_from_text = extract_tracklist_from_text(text_content)
                        if tracks_from_text:
                            tracklist.extend(tracks_from_text)
                    # Also check divs that might contain track listings
                    elif element.name == 'div':
                        text_content = element.text.strip()
                        tracks_from_text = extract_tracklist_from_text(text_content)
                        if tracks_from_text:
                            tracklist.extend(tracks_from_text)
            
            # Check paragraphs that might contain tracklists
            if not tracklist:
                # Look for paragraphs that contain the word "tracklist"
                tracklist_headers = soup.find_all(string=lambda text: text and "tracklist" in text.lower())
                for header in tracklist_headers:
                    element = header.parent
                    # Check next siblings for track-like content
                    for sibling in element.next_siblings:
                        if hasattr(sibling, 'text'):
                            text_content = sibling.text.strip()
                            tracks_from_text = extract_tracklist_from_text(text_content)
                            if tracks_from_text:
                                tracklist.extend(tracks_from_text)
                                break  # Found the tracklist, no need to check more siblings
            
            # Check all paragraphs for track-like content
            if not tracklist:
                p_tags = soup.find_all('p')
                for p in p_tags:
                    text_content = p.text.strip()
                    tracks_from_text = extract_tracklist_from_text(text_content)
                    if tracks_from_text:
                        tracklist.extend(tracks_from_text)
                        break  # Found a tracklist, stop searching

            # Sometimes tracklists are in table format without clear headers
            if not tracklist:
                tables = soup.find_all("table", class_="wikitable")
                for table in tables:
                    rows = table.find_all("tr")
                    for row in rows:
                        # Skip header rows
                        if row.find("th"):
                            continue
                        
                        cols = row.find_all("td")
                        if cols and len(cols) >= 2:  # Typical format: Track number, Track name
                            track_name = cols[1].text.strip()
                            if track_name and not track_name.startswith("?"):
                                track_id = clean_item(track_name)
                                tracklist.append({"track": track_name, "id": track_id})
            
            # Try pre tags if still no tracks found
            if not tracklist:
                pre_tags = soup.find_all("pre")
                for pre_tag in pre_tags:
                    text_content = pre_tag.text.strip()
                    tracks_from_text = extract_tracklist_from_text(text_content)
                    if tracks_from_text:
                        tracklist.extend(tracks_from_text)
                
                # Try parsing from any ol lists that might contain the tracklist
                if not tracklist:
                    ol_tags = soup.find_all("ol")
                    for ol_tag in ol_tags:
                        # Skip if it's inside the already checked tracklist div
                        if ol_tag.find_parent("div", class_="tracklist"):
                            continue
                            
                        li_tags = ol_tag.find_all("li")
                        for li_tag in li_tags:
                            track_name = li_tag.text.strip()
                            if track_name and not track_name.startswith("?"):
                                track_id = clean_item(track_name)
                                tracklist.append({"track": track_name, "id": track_id})
                
                # Look for divs with class "track" which sometimes contain track information
                if not tracklist:
                    track_divs = soup.find_all("div", class_=lambda x: x and "track" in x.lower())
                    for div in track_divs:
                        track_name = div.text.strip()
                        if track_name and not track_name.startswith("?"):
                            track_id = clean_item(track_name)
                            tracklist.append({"track": track_name, "id": track_id})
                
                # Last resort: look for any text with track-like patterns in the main content div
                if not tracklist:
                    content_div = soup.find("div", id="mw-content-text")
                    if content_div:
                        text_content = content_div.get_text()
                        tracks_from_text = extract_tracklist_from_text(text_content)
                        if tracks_from_text:
                            tracklist.extend(tracks_from_text)
        
        # Clean up the tracklist to remove duplicates and validate entries
        if tracklist:
            # Remove duplicates while preserving order
            seen = set()
            tracklist = [x for x in tracklist if not (x['track'] in seen or seen.add(x['track']))]
            
            # Further filter out non-track items
            filtered_tracklist = []
            for item in tracklist:
                track = item['track']
                # Skip items that are just numbers or very short strings
                if re.match(r'^\d+$', track) or len(track) < 4:
                    continue
                # Skip items that are just categories or headers
                if track.lower() in ['tracklist', 'tracks', 'track list', 'setlist', 'set list', 'playlist']:
                    continue
                filtered_tracklist.append(item)
            
            tracklist = filtered_tracklist
            
            logger.info(f"Found a total of {len(tracklist)} tracks for the mix")
        else:
            logger.info("No tracklist found for this mix")
            
        return tracklist
    except Exception as e:
        logger.error(f"Error fetching mix tracklist: {str(e)}")
        return []


def get_total_track_lists_explorer(artist_name):
    """Get the total number of track lists available for an artist in the Explorer view."""
    url = build_explorer_url(artist_name, 0, {})
    
    try:
        response = fetch_with_retry(url)
        soup = BeautifulSoup(response.content, "html.parser")
        
        # Look for the count in the heading
        heading = soup.find('div', class_='rc_headin')
        if heading:
            text = heading.get_text()
            match = re.search(r'\bof\s+(\d+)\b', text)
            if match:
                count = int(match.group(1))
                logger.info(f"Total track lists for {artist_name} from Explorer: {count}")
                return count
        
        # Fallback: Count the actual rows and assume there's only one page
        rows = soup.find_all('tr', class_='spaceRow')
        if rows:
            # Add logic to look for pagination and multiple pages
            pagination = soup.find('div', class_='listPagination')
            if pagination:
                # First look for "x of y" text
                text = pagination.get_text()
                match = re.search(r'\bof\s+(\d+)\b', text)
                if match:
                    count = int(match.group(1))
                    logger.info(f"Found total track lists from pagination: {count}")
                    return count
            
            # If we couldn't find a count, just return the number of rows
            logger.info(f"Counted {len(rows)} track lists in the current page")
            return len(rows)
        
        return 0
    except Exception as e:
        logger.error(f"Error determining total track lists: {str(e)}")
        return 0


def write_to_json(tracklists, filename="tracklists.json"):
    """Write tracklists to a JSON file."""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(tracklists, f, ensure_ascii=False, indent=4)
        logger.info(f"Successfully wrote tracklists to {filename}")
    except Exception as e:
        logger.error(f"Error writing to JSON file: {str(e)}")


def main(artist_name, max_pagination_pages=MAX_PAGINATION_PAGES, max_explorer_mixes=MAX_FETCH_LIMIT):
    """Main function to fetch and process tracklists using both methods with configurable limits."""
    if not artist_name:
        raise ValueError("Artist name is required")
        
    logger.info(f"Processing artist: {artist_name}")
    logger.info(f"Configured limits: Max pagination pages={max_pagination_pages}, Max explorer mixes={max_explorer_mixes}")
    
    # Progress tracking variables
    start_time = time.time()
    processing_step = 1
    total_steps = 4  # Category pages, Explorer pages, Processing, Combining
    
    all_tracklists = []
    
    try:
        # Try both approaches and combine the results
        category_tracklists = []
        explorer_tracklists = []
        
        # First, try the category page approach with pagination support
        logger.info(f"[Step {processing_step}/{total_steps}] Attempting to fetch mixes from Category pages for {artist_name}")
        try:
            # Fetch all pages for this category
            category_pages = fetch_all_category_pages(artist_name, max_pagination_pages)
            
            # Parse each page
            for i, soup in enumerate(category_pages):
                progress = ((i + 1) / len(category_pages)) * 100
                logger.info(f"Parsing category page {i+1} of {len(category_pages)} - {progress:.1f}% complete")
                page_tracklists = parse_category_page(soup, artist_name)
                category_tracklists.extend(page_tracklists)
                
            if category_tracklists:
                logger.info(f"Successfully retrieved {len(category_tracklists)} mixes from all Category pages")
                
                # Count mixes with tracklists
                mixes_with_tracklists = sum(1 for mix in category_tracklists if mix.get("has_tracklist", False))
                logger.info(f"{mixes_with_tracklists} mixes have tracklists from Category pages")
                
                all_tracklists.extend(category_tracklists)
        except Exception as e:
            # Try alternate URL format if the first one fails
            if " " in artist_name and "-" in str(e):
                logger.warning(f"Error with hyphen format URL. Trying underscore format.")
                try:
                    alternate_url = f"{CATEGORY_BASE_URL}{artist_name.replace(' ', '_')}"
                    logger.info(f"Attempting alternate URL: {alternate_url}")
                    response = fetch_with_retry(alternate_url)
                    soup = BeautifulSoup(response.content, "html.parser")
                    category_tracklists = parse_category_page(soup, artist_name)
                    if category_tracklists:
                        logger.info(f"Successfully retrieved {len(category_tracklists)} mixes from alternate Category page")
                        all_tracklists.extend(category_tracklists)
                except Exception as alt_e:
                    logger.warning(f"Error with alternate URL too: {str(alt_e)}. Falling back to Explorer page.")
            else:
                logger.warning(f"Error fetching from Category page: {str(e)}. Falling back to Explorer page.")
        
        processing_step += 1
        
        # Then try the Explorer page approach to find more mixes with tracklists
        logger.info(f"[Step {processing_step}/{total_steps}] Attempting to fetch mixes from Explorer page for {artist_name}")
        try:
            # Get total number of track lists from Explorer
            total_track_lists = get_total_track_lists_explorer(artist_name)
            
            if total_track_lists == 0:
                logger.warning(f"No tracklists found for {artist_name} in Explorer")
            else:
                logger.info(f"Fetching {total_track_lists} tracklists in batches of 25")
                
                # For large catalogs, limit to a reasonable number for better performance
                if total_track_lists > 200:
                    logger.info(f"Large catalog detected ({total_track_lists} mixes). Limiting fetch to prioritize performance.")
                    # Get first X mixes which typically include the most popular ones with tracklists
                    # Respect the user-configured limit
                    max_to_fetch = min(max_explorer_mixes, 200)
                    logger.info(f"Fetching first {max_to_fetch} mixes for faster results")
                else:
                    # For smaller catalogs, fetch up to the limit
                    max_to_fetch = min(total_track_lists, max_explorer_mixes)
                
                for offset in range(0, max_to_fetch, 25):
                    progress = (offset / max_to_fetch) * 100
                    logger.info(f"Fetching batch starting at offset {offset} - {progress:.1f}% complete")
                    soup = fetch_tracklists_explorer(artist_name, offset, {})
                    explorer_batch = parse_tracklists_explorer(soup)
                    explorer_tracklists.extend(explorer_batch)
                    
                    # Report running total of found mixes
                    logger.info(f"Running total: {len(explorer_tracklists)} mixes found so far")
                
                if explorer_tracklists:
                    logger.info(f"Successfully retrieved {len(explorer_tracklists)} mixes from Explorer page")
                    
                    # Count mixes with tracklists
                    explorer_with_tracklists = sum(1 for mix in explorer_tracklists if mix.get("has_tracklist", False))
                    logger.info(f"{explorer_with_tracklists} mixes have tracklists from Explorer page")
                    
                    processing_step += 1
                    logger.info(f"[Step {processing_step}/{total_steps}] Combining results from Category and Explorer pages")
                    
                    # Only add explorer mixes with tracklists if we already have mixes from category page
                    # to avoid duplicate entries
                    if category_tracklists:
                        # Add only explorer mixes with tracklists that have unique titles
                        existing_titles = set(mix["title"] for mix in all_tracklists)
                        unique_added = 0
                        for mix in explorer_tracklists:
                            if mix.get("has_tracklist", False) and mix["title"] not in existing_titles:
                                all_tracklists.append(mix)
                                existing_titles.add(mix["title"])
                                unique_added += 1
                        
                        logger.info(f"Added {unique_added} unique mixes from Explorer that weren't in Category results")
                    else:
                        # If no category mixes, just add all explorer mixes
                        all_tracklists.extend(explorer_tracklists)
                        logger.info(f"No Category results found, using all {len(explorer_tracklists)} mixes from Explorer")
        except Exception as e:
            logger.warning(f"Error fetching from Explorer page: {str(e)}")
        
        processing_step += 1
        logger.info(f"[Step {processing_step}/{total_steps}] Final processing")
        
        # Calculate total tracks for logging
        total_tracks = sum(len(mix.get("tracks", [])) for mix in all_tracklists if mix.get("has_tracklist", False))
        mixes_with_tracklists = sum(1 for mix in all_tracklists if mix.get("has_tracklist", False))
        
        # Calculate execution time
        execution_time = time.time() - start_time
        
        logger.info(f"Processing complete in {execution_time:.2f} seconds")
        logger.info(f"Successfully processed {total_tracks} tracks across {mixes_with_tracklists} mixes with tracklists (total mixes: {len(all_tracklists)})")
        
        # Optionally save to file
        # write_to_json(all_tracklists)
        
        return all_tracklists
        
    except Exception as e:
        logger.error(f"Error in main function for {artist_name}: {str(e)}")
        raise


if __name__ == "__main__":
    try:
        artist = input("Enter artist name: ")
        
        # Get optional configuration parameters
        try:
            max_pages = int(input("Enter maximum pagination pages (default: 10, 0 for unlimited): ") or "10")
            if max_pages <= 0:
                max_pages = float('inf')  # Unlimited
        except ValueError:
            max_pages = MAX_PAGINATION_PAGES
            
        try:
            max_mixes = int(input("Enter maximum explorer mixes to fetch (default: 300, 0 for unlimited): ") or "300")
            if max_mixes <= 0:
                max_mixes = float('inf')  # Unlimited
        except ValueError:
            max_mixes = MAX_FETCH_LIMIT
            
        print(f"Starting search for '{artist}' with max_pages={max_pages}, max_mixes={max_mixes}")
        start_time = time.time()
        
        tracklist = main(artist, max_pages, max_mixes)
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        print(f"Found {len(tracklist)} mixes for {artist} in {execution_time:.2f} seconds")
        print(f"Mixes with tracklists: {sum(1 for mix in tracklist if mix.get('has_tracklist', False))}")
    except Exception as e:
        print(f"Error: {str(e)}")
