import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime, date
from PIL import Image
from io import BytesIO
import pytesseract
from pytesseract import Output

# =========================
# Datum / dag
# =========================
WEEKDAYS = ["måndag", "tisdag", "onsdag", "torsdag", "fredag"]
TODAY_INDEX = datetime.now().weekday()
TODAY = WEEKDAYS[TODAY_INDEX] if TODAY_INDEX < 5 else None
DATE_STR = datetime.now().strftime("%Y-%m-%d")
WEEK = date.today().isocalendar().week

# =========================
# Helpers
# =========================
def fetch_html(url):
    r = requests.get(url, timeout=20)
    r.encoding = "utf-8"
    return r.text

def clean_soup_text(html):
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    return " ".join(soup.stripped_strings)

def extract_day_block(text, day):
    pattern = rf"{day}(.+?)(måndag|tisdag|onsdag|torsdag|fredag|$)"
    m = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    if not m:
        return []

    block = m.group(1)

    lines = re.split(r"(?:Dagens rätt|Dagens fisk|Soppa|Buffé)", block, flags=re.I)
    return [l.strip(" :-") for l in lines if len(l.strip()) > 10]

# =========================
# Gästgivargården
# =========================
def scrape_gastgivargarden():
    html = fetch_html("https://www.gastgivargarden.com/restaurang/dagens-lunch/")
    text = clean_soup_text(html)
    text = re.sub(r"Dagens soppa på buffé\.?", "", text, flags=re.I)
    return extract_day_block(text, TODAY) if TODAY else []

# =========================
# Madame
# =========================
def scrape_madame():
    html = fetch_html("https://madame.se/dagens-lunch/")
    return extract_day_block(clean_soup_text(html), TODAY) if TODAY else []

# =========================
# Hotell Vidöstern (FIX)
# =========================
def scrape_vidostern():
    html = fetch_html("https://www.hotelvidostern.se/matsedeln")
    soup = BeautifulSoup(html, "html.parser")

    for entry in soup.select("div.lunch-entry"):
        day = entry.find("h3")
        if not day:
            continue

        if day.get_text(strip=True).lower() != TODAY:
            continue

        p = entry.find("p")
        if not p:
            return []

        lines = [
            line.strip()
            for line in p.get_text("\n").split("\n")
            if len(line.strip()) > 5
        ]

        return lines

    return []

# =========================
# Rasta Värnamo (NY, HTML-baserad)
# =========================
def scrape_rasta():
    html = fetch_html("https://www.rasta.se/varnamo/dagens-ratt/")
    soup = BeautifulSoup(html, "html.parser")

    for entry in soup.select("div.lunch-entry"):
        day = entry.find("h3")
        if not day:
            continue

        if day.get_text(strip=True).lower() != TODAY:
            continue

        p = entry.find("p")
        if not p:
            return []

        lines = [
            line.strip()
            for line in p.get_text("\n").split("\n")
            if len(line.strip()) > 5
        ]

        return lines

    return []

# =========================
# Vandalorum
# =========================
def scrape_vandalorum():
    html = fetch_html("https://www.vandalorum.se/restaurang")
    soup = BeautifulSoup(html, "html.parser")

    for menu in soup.select("div.menu-div"):
        items = []
        for p in menu.select("p.menu-text"):
            txt = p.get_text(strip=True)
            if not txt or txt.startswith("Inkl. sallad"):
                continue
            items.append(txt)

        if len(items) >= 2:
            return items

    return ["Ingen lunch hittades."]

# =========================
# Matkällaren – REVERT (fungerande version)
# =========================
def find_day_positions(image):
    data = pytesseract.image_to_data(
        image,
        lang="swe",
        output_type=Output.DICT,
        config="--psm 6"
    )

    positions = {}
    for i, word in enumerate(data["text"]):
        w = word.lower().strip(":")
        if w in WEEKDAYS:
            positions[w] = (
                data["left"][i],
                data["top"][i],
                data["width"][i],
                data["height"][i],
            )
    return positions

def crop_day_from_image(image, day):
    positions = find_day_positions(image)
    if day not in positions:
        return None

    y = positions[day][1]
    return image.crop((
        int(image.width * 0.36),
        y,
        int(image.width * 0.97),
        image.height
    ))

def scrape_matkallaren():
    if TODAY_INDEX >= 5:
        return None

    html = fetch_html("https://matkallaren.nu/meny/")
    soup = BeautifulSoup(html, "html.parser")

    img = soup.select_one("div.image-wrap img.wp-post-image")
    if not img:
        return None

    img_data = requests.get(img["src"]).content
    image = Image.open(BytesIO(img_data)).convert("L")

    cropped = crop_day_from_image(image, TODAY)
    if not cropped:
        return None

    filename = "matkallaren_dagens_lunch.png"
    cropped.save(filename)
    return filename

# =========================
# Kör allt
# =========================
data = {
    "Gästgivargården": scrape_gastgivargarden(),
    "Madame": scrape_madame(),
    "Hotell Vidöstern": scrape_vidostern(),
    "Rasta Värnamo": scrape_rasta(),
    "Vandalorum (tis–fre)": scrape_vandalorum(),
}

matkallaren_image = scrape_matkallaren()

# =========================
# HTML
# =========================
html = f"""<!DOCTYPE html>
<html lang="sv">
<head>
<meta charset="UTF-8">
<title>Dagens lunch – {DATE_STR}</title>
<style>

:root {{
    --bg: #faf7f2;
    --card: #fffdf9;
    --text: #2f2a26;
    --muted: #6f665f;
    --accent: #9b5c3c;
    --radius: 12px;
}}

* {{
    box-sizing: border-box;
}}


body {{
    margin: 0;
    padding: 2rem 1rem;
    font-family: system-ui, -apple-system, BlinkMacSystemFont,
                 "Segoe UI", Roboto, sans-serif;
    background: linear-gradient(180deg, #faf7f2 0%, #f1ece5 100%);
    color: var(--text);
}}


h1 {{
    font-size: 1.9rem;
    font-weight: 700;
    margin-bottom: 1.75rem;
    text-align: center;
    color: #3a2f28;
}}

.card {{
    background: var(--card);
    border-radius: var(--radius);
    padding: 1.1rem 1.25rem 1.25rem;
    margin-bottom: 1.25rem;
    border: 1px solid #e6ddd3;
    box-shadow:
        0 6px 18px rgba(0, 0, 0, 0.06),
        inset 0 1px 0 rgba(255, 255, 255, 0.6);
}}

.card h2 {{
    margin: 0 0 0.6rem;
    font-size: 1.2rem;
    font-weight: 600;
    color: var(--accent);
}}


.card ul {{
    margin: 0;
    padding-left: 1.2rem;
}}


.card li {{
    margin-bottom: 0.45rem;
    line-height: 1.45;
}}


.card li::marker {{
    color: var(--accent);
}}

.card img {{
    display: block;
    margin-top: 0.6rem;
    border-radius: 8px;
    max-width: 100%;
    border: 1px solid #e6ddd3;
}}

em {{
    color: var(--muted);
    font-style: normal;
    font-size: 0.9rem;
}}

</style>
</head>
<body>

<h1>Dagens lunch – {TODAY.capitalize() if TODAY else "Helg"} – V. {WEEK}</h1>
"""

for name, items in data.items():
    html += f"<div class='card'><h2>{name}</h2><ul>"
    for item in items:
        html += f"<li>{item}</li>"
    html += "</ul></div>"

html += "<div class='card'><h2>Matkällaren</h2>"
if matkallaren_image and TODAY != "fredag":
    html += f"<img src='{matkallaren_image}'>"

if TODAY == "fredag":
    html += "<p><em>Schnitzelfredag!!</em></p>"

if not matkallaren_image:
    html += "<p><em>Menyn publiceras som bild – se matkallaren.nu</em></p>"

html += "</div></body></html>"

with open("dagens_lunch.html", "w", encoding="utf-8") as f:
    f.write(html)

print("Dagens lunch genererad")
