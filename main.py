import requests
import json
from urllib.parse import urlencode
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0"}

total_track_lists = 0

def build_url(offset, other_params):
    base_url = "https://www.mixesdb.com/w/MixesDB:Explorer/Mixes"
    params = {
        "do": "mx",
        "mode": "",
        "cat1": "Ben UFO",
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



def fetch_tracklists(offset, other_params):
    url = build_url(offset, other_params)
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
                tracklist.append(li_tag.text.strip())
        if tracklist:
            tracklists.append(tracklist)
    return tracklists

def write_to_json(tracklists, filename="tracklists.json"):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(tracklists, f, ensure_ascii=False, indent=4)

def main():
    total_track_lists = 295  # or you can dynamically find this value
    all_tracklists = []
    for offset in range(0, total_track_lists, 25):
        soup = fetch_tracklists(offset, {})
        tracklists = parse_tracklists(soup)
        all_tracklists.extend(tracklists)
    write_to_json(all_tracklists)

if __name__ == "__main__":
    main()
    