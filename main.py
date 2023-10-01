import requests
import json
from urllib.parse import urlencode
from bs4 import BeautifulSoup

from clean_item import clean_item

HEADERS = {"User-Agent": "Mozilla/5.0"}

total_track_lists = 0


def build_url(artist_name, offset, other_params):
    base_url = "https://www.mixesdb.com/w/MixesDB:Explorer/Mixes"
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
    return f"{base_url}?{query_string}"


def fetch_tracklists(artist_name, offset, other_params):
    url = build_url(artist_name, offset, other_params)
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()
    return BeautifulSoup(response.content, "html.parser")


def parse_tracklists(soup):
    tracklists = []
    for explorerResult in soup.find_all("div", class_="explorerResult"):
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
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(tracklists, f, ensure_ascii=False, indent=4)


def main(artist_name):
    print("ARTIST_NAME: ", artist_name)

    print("fetching total number of tracks...")

    dynamic_url = build_url(artist_name, 0, {})
    page = requests.get(dynamic_url, headers=HEADERS)

    if not page.status_code == 200:
        print("Not able to fetch the url...")

    soup = BeautifulSoup(page.content, "html.parser")

    # Get total number of track lists
    exploreRes_class = soup.find("span", class_="explorerRes")
    b_tag_in_explorerRes_class = exploreRes_class.find("b")
    total_track_lists = b_tag_in_explorerRes_class.text.strip()

    print("TOTAL_TRACK_LISTS: ", total_track_lists)

    all_tracklists = []
    print("parsing tracks...")
    for offset in range(0, int(total_track_lists), 25):
        soup = fetch_tracklists(artist_name, offset, {})
        tracklists = parse_tracklists(soup)
        all_tracklists.extend(tracklists)
    flat_tracklist = [track for sublist in all_tracklists for track in sublist]
    return flat_tracklist


if __name__ == "__main__":
    main()
