import re
import unicodedata # Import unicodedata
# import requests

from urllib.parse import quote

url = "https://www.mixesdb.com/tools/api/apiAffTracklists.php"

def clean_item(item):

    # Define a regular expression pattern for matching substrings enclosed in square brackets
    bracket_pattern = re.compile(r'\[.*?\]')

    # Define a regular expression pattern for matching special characters including "&", long-dashes, "+", and non-breaking spaces
    # Removed some punctuation to be less aggressive if needed, focus on problematic chars
    special_char_pattern = re.compile(r"[<>\":\-(){}_&—–+]|\xa0") 

    # Define a regular expression pattern for matching words "mix" and "remix" inside brackets
    mix_remix_pattern = re.compile(r'\((.*?)(mix|remix|edit)(.*?)\)')

    # 1. Remove text within square brackets
    cleaned_item = bracket_pattern.sub('', item).strip()
    
    # 2. Normalize unicode characters (e.g., convert fancy quotes/dashes)
    try:
        cleaned_item = unicodedata.normalize('NFKD', cleaned_item)
    except TypeError:
        pass # Ignore if item is not a string (shouldn't happen)

    # 3. Encode to ASCII ignoring errors, then decode back to remove strange chars
    # This is quite aggressive but often effective
    cleaned_item = cleaned_item.encode('ascii', 'ignore').decode('ascii')

    # 4. Convert to lowercase AFTER normalization/encoding
    cleaned_item = cleaned_item.lower()

    # 5. Replace occurrences of "mix" or "remix" inside brackets (might be less relevant after encoding)
    cleaned_item = mix_remix_pattern.sub(
        lambda m: f"({m.group(1).strip() + ' ' + m.group(3).strip()})", cleaned_item)

    # 6. Remove specific special characters (less aggressive now)
    cleaned_item = special_char_pattern.sub('', cleaned_item)
    
    # 7. Remove any remaining non-alphanumeric characters (except space)
    # This is even more aggressive
    cleaned_item = re.sub(r'[^a-z0-9\s]+', '', cleaned_item)

    # 8. Ensure there is only one space between words
    cleaned_item = ' '.join(cleaned_item.split())

    # Return the cleaned string (URL encoding is likely not needed here anymore if this is for PDF)
    # If the ID returned is used elsewhere and NEEDS encoding, keep it.
    # For PDF display, we want the cleaned human-readable string.
    # encoded_cleaned_item = quote(cleaned_item)
    # return encoded_cleaned_item
    return cleaned_item # Return plain cleaned string for PDF


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