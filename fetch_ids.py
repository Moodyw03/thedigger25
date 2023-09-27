import re
import requests

from urllib.parse import quote

url = "https://www.mixesdb.com/tools/api/apiAffTracklists.php"

data = [
    "[000] Efdemin - America [Curle - 016]",
    "[005] Temporary Permanence - Peculiar",
    "[011] VC-118A - Elektri [Delsin - 157DSR]",
    "[016] Grad_U - Reprise [Greyscale - GRSCL01]",
    "[021] Submeditation - Back In Space [Cancelled - CNLD099]",
    "[027] DJ Qu - Everybody's Dark [Soul People Music - SPMETV002]",
    "[032] Markus Suckut - Pressure",
    "[038] Vardae - Kaipo [OODA1]",
    "[042] Patrice Scott - Motion Beats [Sistrum - SIS 004]",
    "[045] Edward - Sender [Sushitech - SUSH52]",
    "[050] Mathew Jonson - Love Letter To The Enemy [Itiswhatitis - IIWII009]",
    "[059] Ryuichi Sakamoto - A Painful Memory [Commons]",
    "[062] Francis Harris - Minor Forms (Valentino Mora Cosmic Trans Rephase) [Scissor And Thread - SAT034]",
    "[068] Antias - Nordic [LDN Trax - LDV128]",
    "[070] Kano Kanape - Goliath (Matthias Springer Remix) [Zero413 - O413LTD005]",
    "[076] Subground 3000 - North Side [DimbiDeep - DIMBI048]",
    "[081] Tasoko - Evoke [Dred - DREDLP001]",
    "[084] Andrum - Underwater [Seventh Sign - 7SR026]",
    "[089] Nick Dunton - Leaving The Planet [Surface - SF BSF 003]",
    "[093] Tender H - Constellation [DimbiDeep - DIMBI054]",
    "[097] ?",
    "[101] Andres Hellberg - Krakel [Discrete Data - DSD06]",
    "[105] Pisetzky - Eran (Antonio Ruscito Remix) [Discrete Data - DSD06]",
    "[109] Sterac - Satyricon [100% Pure - PURE LP 1]",
    "[113] ?",
    "[116] RVSHES - MTS/RHS VI [Delsin - DSR/MTS12]",
    "[118] Hansgod - Trim Line [EP Digital Music - DPDM40.0]",
    "[123] ?",
    "[127] ?"
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
