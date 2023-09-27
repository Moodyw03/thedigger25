# import requests
# from bs4 import BeautifulSoup

# URL = "https://www.mixesdb.com/w/2008-06-18_-_Ben_UFO_-_FACT_Mix_08"
# HEADERS = {"User-Agent": "Mozilla/5.0"}

# page = requests.get(URL, headers=HEADERS)

# if page.status_code == 200:
#     soup = BeautifulSoup(page.content, "html.parser")
#     # script = soup.find('script')
#     # script_text = script.text

#     # pattern = re.compile(r'data-youtubeid="([-\w]+)"')
#     # youtube_ids = re.findall(pattern, script_text)

#     # print(youtube_ids)
#     print(soup)

#     # Find the element with id 'tracklist'
#     tracklist = soup.find(id="Tracklist")
#     # print(tracklist)
#     # Initialize a list to store the extracted elements
#     extracted_elements = []

#     # If the 'tracklist' element is found, find all adjacent <dl> and <ol> tags
#     # until the element with id 'bodyBottom' is encountered
#     if tracklist:
#         for sibling in tracklist.find_all_next():
#             # print(sibling)
#             # If the sibling has id 'bodyBottom', break the loop
#             if sibling.get('id') == 'bodyBottom':
#                 break
#             # If the sibling is <dl> or <ol>, append it to the list of extracted elements
#             elif sibling.name in ['dl', 'ol']:
#                 extracted_elements.append(sibling)


#     # Display the extracted elements
#     for element in extracted_elements:
#         # print(element.prettify())
#         li_elements = element.find_all("li")
#         for ele in li_elements:
#             print(ele.find("span"))
#             print(ele.text.strip())
#             span = ele.find("span")
#             if span and 'data-youtubeid' in span.attrs:
#                 print(f"data-youtubeid: {span['data-youtubeid']}")
#                 print(f"Text: {ele.text.strip()}")


# # soup = BeautifulSoup(page.content, "html.parser")


# # Find element by ID
# # results = soup.find(id="ResultsContainer")
# # print(results.prettify())
# # python_jobs = results.find_all("h2", string="Python")
# # python_jobs = results.find_all(
# #   "h2", string=lambda text: "python" in text.lower()
# # )

# # python_job_elements = [
# #   h2_element.parent.parent.parent for h2_element in python_jobs
# # ]

# # for job_element in python_job_elements:
# #   title_element = job_element.find("h2", class_="title")
# #   company_element = job_element.find("h3", class_="company")
# #   location_element = job_element.find("p", class_="location")
# #   print(title_element.text.strip())
# #   print(company_element.text.strip())
# #   print(location_element.text.strip())
# #   print()
# #   links = job_element.find_all("a")
# #   for link in links:
# #     link_url = link["href"]
# #     print(link_url)
# #   print()

# # Find element by Class
# # job_elements = results.find_all("div", class_="card-content")
# # print(job_elements[0].prettify())

# # for job_element in job_elements:
# #   title_element = job_element.find("h2", class_="title")
# #   company_element = job_element.find("h3", class_="company")
# #   location_element = job_element.find("p", class_="location")
# #   print(title_element.text.strip())
# #   print(company_element.text.strip())
# #   print(location_element.text.strip())
# #   print()


# #############
# import requests
# import json
# import re
# from bs4 import BeautifulSoup

# URL = "https://www.mixesdb.com/w/2008-06-18_-_Ben_UFO_-_FACT_Mix_08"
# HEADERS = {"User-Agent": "Mozilla/5.0"}

# page = requests.get(URL, headers=HEADERS)

# if page.status_code == 200:
#     soup = BeautifulSoup(page.content, "html.parser")

#     # Find the script tag containing the JavaScript object
#     script_tag = soup.find("script", text=re.compile("mw.config.set"))

#     if script_tag:
#         # Extract the JavaScript object string using a regular expression
#         js_object_str = re.search("mw.config.set\((\{.*?\})\);", script_tag.string, re.DOTALL)

#         if js_object_str:
#             # Load the JavaScript object string as a Python dictionary
#             js_object = json.loads(js_object_str.group(1))

#             # Extract the desired data
#             encoded_html = js_object.get("pageAffTl", {}).get("tl", "")

#             # Parse the encoded HTML string with BeautifulSoup
#             encoded_soup = BeautifulSoup(encoded_html, "html.parser")

#             for li in encoded_soup.find_all("li"):
#                 print(li.text)
#                 span = li.find("span", {"data-youtubeid": True})
#                 if span:
#                     print(span["data-youtubeid"])
#                     print()
#                     print(":::::::::::::::::::::::")
#                     print()


# div.explorerResult[] > div.ExplorerTracklist > ol > li > text > strip()


# div.explorerResult[] > div.ExplorerTracklist > ol[] > li > text > strip

import requests
import json
from urllib.parse import urlencode
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0"}

total_track_lists = 0

def build_url(do="", mode="", cat1="", cat2="", jnc="", style="", year="",
              tlc="", tli="", so="", tmatch1="", tmatch2="", jntm="", usesFile="",
              minHotnessLevel="", count="25", order="name", sort="", offset=""):

    base_url = "https://www.mixesdb.com/w/MixesDB:Explorer/Mixes"

    # This is a long comment. This should be wrapped to fit within 72 characters.
    query_params_order = [
        ("do", do),
        ("mode", mode),
        ("cat1", cat1),
        ("cat2", cat2),
        ("jnC", jnc),
        ("style", style),
        ("year", year),
        ("tlC", tlc),
        ("tlI", tli),
        ("so", so),
        ("tmatch1", tmatch1),
        ("tmatch2", tmatch2),
        ("jnTm", jntm),
        ("usesFile", usesFile),
        ("minHotnessLevel", minHotnessLevel),
        ("count", count),
        ("order", order),
        ("sort", sort),
        ("offset", offset)
    ]

    query_string = urlencode(query_params_order)

    return f"{base_url}?{query_string}"


# Usage
dynamic_url = build_url(do="mx", cat1="Ben UFO", tlc="1", tli="1", sort="desc", offset="1")
print(dynamic_url)


page = requests.get(dynamic_url, headers=HEADERS)

if not page.status_code == 200:
    print("Not able to fetch the url...")

soup = BeautifulSoup(page.content, "html.parser")

# Get total number of track lists
exploreRes_class = soup.find("span", class_="explorerRes")
b_tag_in_explorerRes_class = exploreRes_class.find("b")
total_track_lists = b_tag_in_explorerRes_class.text.strip()

# Get all the tracks in lists
explorerResult_classes = soup.find_all("div", class_="explorerResult")

if len(explorerResult_classes) < 1:
    print("No tracklist found.")

list_counter = 0
tracks_counter = 0

for explorerResult_class in explorerResult_classes:
    explorerTracklist_class = explorerResult_class.find("div", class_="ExplorerTracklist")
    if not explorerTracklist_class:
        print("this list is skipped.")
        continue
    ol_in_explorerTracklist_class_array = explorerTracklist_class.find_all("ol");
    if len(ol_in_explorerTracklist_class_array) < 1:
        print("No records in this list...")
        continue
    list_counter = list_counter + 1
    for ol_in_explorerTracklist_class in ol_in_explorerTracklist_class_array:
        li_in_ol_in_explorerTracklist_class_array = ol_in_explorerTracklist_class.find_all("li")
        if len(li_in_ol_in_explorerTracklist_class_array) < 1:
            print("this list is empty")
        for li_in_ol_in_explorerTracklist_class in li_in_ol_in_explorerTracklist_class_array:
            print(li_in_ol_in_explorerTracklist_class.text.strip())
            tracks_counter = tracks_counter + 1

print("Total lists:", list_counter)
print("Total tracks:", tracks_counter)
    