import re
import requests

from urllib.parse import quote

url = "https://www.mixesdb.com/tools/api/apiAffTracklists.php"

data = [
    "[000] Princess Diana Of Wales - Cut [A Colourful Storm - INTIM001]",
    "[006] Nate Scheible - Plumbe05",
    "[009] Polygonia - ITiTi [Phase Imprint - PHASESNGL001]",
    "[012] Shackleton - You Bring Me Down (Peverelist Remix) [Skull Disco - SKULLCD002II]",
    "[014] Call Super & Julia Holter - Illumina [Can You Feel The Sun - CYFUSOUL]",
    "[018] OHM - Tribal Tone (Sabres Mix 1) [Hubba Hubba - HUB 011]",
    "[022] Nubian Mindz - Aqua Lifeforms [Barba - BAR010]",
    "[025] Mere Mortals - Shift [Map - MAP202-2]",
    "[028] 4E - Ask Isadora (Fit Edit) [Fit Sound - FIT-023]",
    "[032] Sage - Orchid Dance",
    "[035] Batu - Traverse [A Long Strange Dream - ALSD001]",
    "[038] Ayesha - ?",
    "[041] Black Jazz Consortium - Rebirth Groove",
    "[053] David Alvarado - Beautification [Peacefrog - PFG010LP]",
    "[055] Gypsy - Funk De Fino [Limbo - LIMB31T]",
    "[060] Dashiell - This Colourful World [Pollinate - POLN02]",
    "[064] Torei - Fish Shooter [Set Fire To Me - SFTM001]",
    "[067] Dave Angel - Original Man [Aura Surround Sounds - AUSS 001]",
    "[072] ?",
    "[077] Cousin - Manta [Moonshoe - MSH011]",
    "[080] Soichi Terada - タイムステーション / Time Station [Far East - FER06902]",
    "[085] Olof Deijer & Mount Sims - Hybrid Fruit [Rabid - RABID090]",
    "[093] ?",
    "[097] ?",
    "[101] ?",
    "[108] ?",
    "[112] Robag Wruhme - Kapox Graphén [Tulpa Ovi - T.O.R. 006]",
    "[114] Dub & Wheel - Judgement [Future Retro London - FR015]"
]


def clean_data(data):
    cleaned_data = []

    # Define a regular expression pattern for matching substrings enclosed in square brackets
    bracket_pattern = re.compile(r'\[.*?\]')

    # Define a regular expression pattern for matching special characters
    special_char_pattern = re.compile(r"[,./;'<>?\":\-(){}_&—–]")

    # Define a regular expression pattern for matching words "mix" and "remix" inside brackets
    mix_remix_pattern = re.compile(r'\((.*?)(mix|remix|edit)(.*?)\)')

    for item in data:
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

        cleaned_data.append(cleaned_item)

    return cleaned_data


# Call the function and store the result in cleaned_data
cleaned_data = clean_data(data)

# Now, cleaned_data contains the cleaned strings.

for d in cleaned_data:
    encoded_d = quote(d)


    payload = {'trackSearch': encoded_d}
    files = [

    ]
    headers = {"User-Agent": "Mozilla/5.0"}

    response = requests.request("POST", url, headers=headers, data=payload, files=files)

    print(response.text)
