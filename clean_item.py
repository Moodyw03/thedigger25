import re
# import requests

from urllib.parse import quote

url = "https://www.mixesdb.com/tools/api/apiAffTracklists.php"

def clean_item(item):

    # Define a regular expression pattern for matching substrings enclosed in square brackets
    bracket_pattern = re.compile(r'\[.*?\]')

    # Define a regular expression pattern for matching special characters including "&", long-dashes, and "+"
    special_char_pattern = re.compile(r"[,./;'<>?\":\-(){}_&—–+]")


    # Define a regular expression pattern for matching words "mix" and "remix" inside brackets
    mix_remix_pattern = re.compile(r'\((.*?)(mix|remix|edit)(.*?)\)')

    # Remove text within square brackets
    cleaned_item = bracket_pattern.sub('', item).strip()

    # Convert to lowercase
    cleaned_item = cleaned_item.lower()

    # Replace occurrences of "mix" or "remix" inside brackets
    cleaned_item = mix_remix_pattern.sub(
        lambda m: f"({m.group(1).strip() + ' ' + m.group(3).strip()})", cleaned_item)

    # Remove other special characters
    cleaned_item = special_char_pattern.sub('', cleaned_item)

    # Ensure there is only one space between words
    cleaned_item = ' '.join(cleaned_item.split())

    encoded_cleaned_item = quote(cleaned_item)

    return encoded_cleaned_item


# # Call the function and store the result in cleaned_data
# cleaned_item = clean_item("[03] KANDY & Purge - Pause [Free Track]")

# # Now, cleaned_data contains the cleaned strings.

# payload = {'trackSearch': cleaned_item}
# files = [

# ]
# headers = {"User-Agent": "Mozilla/5.0"}

# response = requests.request("POST", url, headers=headers, data=payload, files=files)

# print(response.text)


if __name__ == "__clean_item__":
    clean_item()