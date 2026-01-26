import requests
import re
from bs4 import BeautifulSoup, NavigableString
from datetime import datetime, date
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
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
TODAY_WEEK = date.today()
WEEK = TODAY_WEEK.isocalendar().week

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

    split_keywords = [
        "Dagens rätt", "Dagens", "Soppa", "Veckans soppa",
        "Buffé", "Julbuffé"
    ]

    lines = []
    current = ""

    for word in block.split():
        if any(word.lower().startswith(k.lower()) for k in split_keywords):
            if current:
                lines.append(current.strip())
            current = word
        else:
            current += " " + word

    if current:
        lines.append(current.strip())

    return [l for l in lines if len(l) > 5]

# =========================
# Gästgivargården
# =========================
def scrape_gastgivargarden():
    html = fetch_html("https://www.gastgivargarden.com/restaurang/dagens-lunch/")
    text = clean_soup_text(html)

    text = text.replace("Dagens soppa på buffé.", "")
    text = text.replace("Dagens soppa på buffé", "")

    return extract_day_block(text, TODAY) if TODAY else []

# =========================
# Madame
# =========================
def scrape_madame():
    html = fetch_html("https://madame.se/dagens-lunch/")
    soup = BeautifulSoup(html, "html.parser")

    container = soup.find("div", class_="lunch_weekdays")
    if not container:
        return []

    for h5 in container.find_all("h5"):
        day_text = h5.get_text(strip=True).lower()

        if day_text != TODAY:
            continue

        dish_p = h5.find_next("p", class_="main_dish")
        if not dish_p:
            return []

        dish = dish_p.get_text(strip=True)
        return [dish]

    return []

# =========================
# Vandalorum
# =========================
def scrape_vandalorum():
    html = fetch_html("https://www.vandalorum.se/restaurang")
    soup = BeautifulSoup(html, "html.parser")

    menu_divs = soup.select("div.menu-div")
    if not menu_divs:
        return ["Ingen lunch hittades."]

    for menu in menu_divs:
        items = []
        for p in menu.select("p.menu-text"):
            txt = p.get_text(strip=True)
            if not txt:
                continue
            if txt.startswith("Inkl. sallad"):
                return items
            items.append(txt)

        if len(items) >= 2:
            return items

    return ["Ingen lunch hittades."]


# =========================
# Rasta
# =========================
def scrape_rasta():
    html = fetch_html("https://www.rasta.se/varnamo/dagens-ratt/")
    soup = BeautifulSoup(html, "html.parser")

    for entry in soup.select("div.lunch-entry"):
        day_tag = entry.find("h3")
        if not day_tag:
            continue

        # normalisera bort osynliga tecken
        day_text = (
            day_tag.get_text(strip=True)
            .lower()
            .replace("\u200b", "")
            .replace("\xa0", "")
        )

        if TODAY not in day_text:
            continue

        p = entry.find("p")
        if not p:
            continue

        lines = []
        for line in p.get_text("\n").split("\n"):
            clean = line.strip()
            if not clean:
                continue
            if clean.lower() == "dagens fisk":
                continue
            lines.append(clean)

        return lines

    return []


# =========================
# Vidöstern
# =========================
def scrape_vidostern():
    html = fetch_html("https://www.hotelvidostern.se/matsedeln")
    soup = BeautifulSoup(html, "html.parser")

    container = soup.find("div", class_="article-dynamic-template-content")
    if not container or not TODAY:
        return []

    weekdays = ["måndag", "tisdag", "onsdag", "torsdag", "fredag", "lördag", "söndag"]

    collecting = False
    items = []

    for node in container.children:
        if isinstance(node, str):
            text = node.strip()
        else:
            text = node.get_text(" ", strip=True)

        if not text:
            continue

        lowered = text.lower()

        if lowered in weekdays:
            if lowered == TODAY:
                collecting = True
                items = []
                continue
            if collecting:
                break
            continue

        if not collecting:
            continue

        if (
            "pris" in lowered
            or "serveras mellan" in lowered
            or "pensionär" in lowered
            or "välkommen" in lowered
            or "information" in lowered
            or "kockens val" in lowered
        ):
            continue

        items.append(text)

    return items



# =========================
# Matkällaren – bildigenkänning
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
        if not word:
            continue

        normalized = word.lower().strip(":").strip()

        if normalized in WEEKDAYS:
            x = data["left"][i]
            y = data["top"][i]
            w = data["width"][i]
            h = data["height"][i]

            if normalized not in positions:
                positions[normalized] = (x, y, w, h)

    return positions



def crop_day_from_image(image, day):
    positions = find_day_positions(image)
    if day not in positions:
        return None

    sorted_days = sorted(positions.items(), key=lambda x: x[1][1]) 

    for i, (d, (x, y, w, h)) in enumerate(sorted_days):
        if d == day:
            top = y
            bottom = (
                sorted_days[i + 1][1][1]
                if i + 1 < len(sorted_days)
                else image.height
            )

            left  = int(image.width * 0.36)   # kapa % från vänster
            right = int(image.width * 0.97)   # kapa % från höger


            return image.crop((left, top, right, bottom))

    return None



def scrape_matkallaren():

    if TODAY_INDEX >= 5:
        return None

    menu_page = "https://matkallaren.nu/meny/"

    try:
        r = requests.get(menu_page, timeout=20)
    except Exception as e:
        print("Matkällaren: kunde inte hämta menysidan:", e)
        return None

    if r.status_code != 200:
        print("Matkällaren: menysidan returnerade", r.status_code)
        return None

    soup = BeautifulSoup(r.text, "html.parser")

    menu_img = None

    for img in soup.find_all("img"):
        classes = img.get("class", [])
        title = (img.get("title") or "").lower()
        alt = (img.get("alt") or "").lower()

        if (
            "wp-post-image" in classes
            and "meny" in title
        ):
            menu_img = img
            break

    if not menu_img or not menu_img.get("src"):
        print("Matkällaren: kunde inte identifiera rätt menybild")
        return None

    image_url = menu_img["src"]
    print("Matkällaren: hittade menybild:", image_url)


    try:
        img_response = requests.get(image_url, timeout=20)
    except Exception as e:
        print("Matkällaren: kunde inte hämta bilden:", e)
        return None

    if img_response.status_code != 200:
        print("Matkällaren: bilden returnerade", img_response.status_code)
        return None

    if not img_response.headers.get("Content-Type", "").startswith("image"):
        print("Matkällaren: URL returnerade inte en bild")
        return None

    try:
        img = Image.open(BytesIO(img_response.content))
    except UnidentifiedImageError:
        print("Matkällaren: PIL kunde inte identifiera bilden")
        return None

    img = img.convert("L")

    cropped = crop_day_from_image(img, TODAY)
    if not cropped:
        print("Matkällaren: kunde inte hitta dagens rubrik i bilden")
        return None

    filename = "matkallaren_dagens_lunch.png"
    cropped.save(filename)
    print("Matkällaren: bild sparad:", filename)

    return filename




# =========================
# Kör allt
# =========================
data = {
    "Gästgivargården": scrape_gastgivargarden(),
    "Madame": scrape_madame(),
    "Vandalorum (tis–fre)": scrape_vandalorum(),
    "Vidöstern": scrape_vidostern()
    #"Rasta": scrape_rasta()
}

matkallaren_image = scrape_matkallaren()

# =========================
# HTML
# =========================
html = f"""<!DOCTYPE html>
<html lang="sv">
<head>
<meta charset="UTF-8" http-equiv="refresh" content="60">
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

<h1>Dagens lunch – {TODAY.capitalize() if TODAY else "Helg"} - V. {WEEK}</h1>
"""

for name, items in data.items():
    html += f"<div class='card'><h2>{name}</h2><ul>"
    for item in items:
        html += f"<li>{item}</li>"
    html += "</ul></div>"

html += "<div class='card'><h2>Matkällaren</h2>"
if matkallaren_image and TODAY != 'fredag':
    html += f"<img src='{matkallaren_image}' style='max-width:100%; border-radius:8px;'>"

if TODAY == 'fredag':
    html += "<ul><li>Schnitzelfredag!!</li></ul>"

if not matkallaren_image:
    html += "<p><h2>Menyn publiceras som bild – se matkallaren.nu</h2></p>"
html += "</div>"

html += "</body></html>"

with open("dagens_lunch.html", "w", encoding="utf-8") as f:
    f.write(html)

print("Dagens lunch genererad")
