import requests
import time
import json
import re
from urllib.parse import quote
from bs4 import BeautifulSoup

BASE_URL = "https://www.mixesdb.com"

HEADERS = {"User-Agent": "Mozilla/5.0"}

def get_artist_data(artist_name):
    # encoded_input = quote(artist_name)
    SEARCH_URL = f'https://www.mixesdb.com/db/index.php?title=Special:Search&limit=100&offset=0&profile=mixes&search={artist_name}'

    page = requests.get(SEARCH_URL, headers=HEADERS)

    if page.status_code!=200:
        return "Unable to reach the page"

    soup = BeautifulSoup(page.content, "html.parser")

    page_title_list_element = soup.select_one('#Page_title_matches + .mw-search-results')

    list_of_titles =  page_title_list_element.find_all("a", class_="cat-tlC")

    data = []

    for anchor in list_of_titles:
        title = anchor.text
        link = BASE_URL + anchor["href"]
        data.append({"title": title, "link": link})

    return data

def get_tracklists(artist_data):
    start_time = time.time()   # start time

    counter = 0

    tracks = []

    for artist in artist_data:
        print(artist["link"])
        page = requests.get(artist["link"], headers=HEADERS)

        
        if page.status_code != 200:
            continue

        soup = BeautifulSoup(page.content, "html.parser")
        
        # Find the script tag containing the JavaScript object
        script_tag = soup.find("script", string=re.compile("mw.config.set"))
        
        if not script_tag:
            continue

        # Extract the JavaScript object string using a regular expression
        js_object_str = re.search("mw.config.set\((\{.*?\})\);", script_tag.string, re.DOTALL)
        
        if not js_object_str:
            continue

        # Load the JavaScript object string as a Python dictionary
        js_object = json.loads(js_object_str.group(1))
        
        # Extract the desired data
        encoded_html = js_object.get("pageAffTl", {}).get("tl", "")
        
        if not encoded_html:
            continue

        # Parse the encoded HTML string with BeautifulSoup
        encoded_soup = BeautifulSoup(encoded_html, "html.parser")
        
        # Extract track title and YouTube ID from the parsed HTML
        for li in encoded_soup.find_all("li"):
            span = li.find("span")
            if span:
                title_of_track = li.text
                yt_id_of_track = span.get("data-youtubeid") if span else "-1"
                tracks.append({"titleOfTrack": title_of_track, "ytIdOfTrack": yt_id_of_track})
                counter = counter + 1
                print("🔢:", counter)
                print(title_of_track)
                print(yt_id_of_track)
                print("🕹️🕹️🕹️🕹️🕹️🕹️🕹️🕹️🕹️🕹️🕹️🕹️🕹️🕹️🕹️")

    end_time = time.time()   # end time
    time_lapsed = end_time - start_time  # time lapsed
    print("Time lapsed to run the function: {} seconds".format(time_lapsed))
    print("Counted:", counter)

    print(len(tracks))
        
    return json.dumps(tracks, indent=2) 


        


# usage

# TODO: make it a user input
artist_name = input("Enter artist: ")

# artist_name = "Ben UFO"   # replace with user input
artist_data = get_artist_data(artist_name)
dataFetched = get_tracklists(artist_data)
print(dataFetched)
print(len(dataFetched))
