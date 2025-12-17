import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime
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
    return extract_day_block(text, TODAY) if TODAY else []

# =========================
# Madame
# =========================
def scrape_madame():
    html = fetch_html("https://madame.se/dagens-lunch/")
    text = clean_soup_text(html)
    return extract_day_block(text, TODAY) if TODAY else []

# =========================
# Vandalorum (DOM-baserad)
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

    sorted_days = sorted(positions.items(), key=lambda x: x[1][1])  # sortera på y

    for i, (d, (x, y, w, h)) in enumerate(sorted_days):
        if d == day:
            top = y
            bottom = (
                sorted_days[i + 1][1][1]
                if i + 1 < len(sorted_days)
                else image.height
            )

            # 🔧 TIGHTARE HORISONTELL CROP
            left = max(0, x - 20)
            right = min(image.width, x + w + 440)

            return image.crop((left, top, right, bottom))

    return None



def scrape_matkallaren():
    if TODAY_INDEX >= 5:
        return None

    week = datetime.now().isocalendar().week
    image_url = f"https://matkallaren.nu/wp-content/uploads/sites/1341/2025/12/meny-v-{week}.png"

    img_data = requests.get(image_url, timeout=20).content
    img = Image.open(BytesIO(img_data))

    img = img.convert("L")
    img = ImageOps.autocontrast(img)
    img = img.filter(ImageFilter.SHARPEN)

    cropped = crop_day_from_image(img, TODAY)
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
    "Vandalorum (tis–fre)": scrape_vandalorum()
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
body {{
    font-family: system-ui;
    background: #f5f5f5;
    padding: 2rem;
}}
.card {{
    background: white;
    padding: 1.5rem;
    border-radius: 10px;
    margin-bottom: 1.2rem;
    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
}}
</style>
</head>
<body>

<h1>Dagens lunch – {TODAY.capitalize() if TODAY else "Helg"}</h1>
"""

for name, items in data.items():
    html += f"<div class='card'><h2>{name}</h2><ul>"
    for item in items:
        html += f"<li>{item}</li>"
    html += "</ul></div>"

html += "<div class='card'><h2>Matkällaren</h2>"
if matkallaren_image:
    html += f"<img src='{matkallaren_image}' style='max-width:100%; border-radius:8px;'>"
else:
    html += "<p><em>Menyn publiceras som bild – se matkallaren.nu</em></p>"
html += "</div>"

html += "</body></html>"

with open("dagens_lunch.html", "w", encoding="utf-8") as f:
    f.write(html)

print("✅ Dagens lunch genererad")
