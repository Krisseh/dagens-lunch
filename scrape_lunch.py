import requests
from bs4 import BeautifulSoup
from datetime import datetime
import re
from PIL import Image
import pytesseract
from io import BytesIO

# -----------------------------
# Datum & veckodag
# -----------------------------
WEEKDAYS = ["måndag", "tisdag", "onsdag", "torsdag", "fredag"]
TODAY = WEEKDAYS[datetime.now().weekday()] if datetime.now().weekday() < 5 else None
DATE_STR = datetime.now().strftime("%Y-%m-%d")

# -----------------------------
# Hjälpfunktioner
# -----------------------------
def fetch_html(url):
    return requests.get(url, timeout=15).text

def clean_soup_text(html):
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    return " ".join(soup.stripped_strings)

def extract_day_block(text, day):
    pattern = rf"{day}(.+?)(måndag|tisdag|onsdag|torsdag|fredag|$)"
    match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    if match:
        block = match.group(1)
        lines = [l.strip() for l in block.splitlines() if len(l.strip()) > 3]
        return lines
    return []

# -----------------------------
# OCR-modul
# -----------------------------
def ocr_image_from_url(image_url):
    try:
        img_data = requests.get(image_url, timeout=15).content
        img = Image.open(BytesIO(img_data))
        text = pytesseract.image_to_string(
            img,
            lang="swe",
            config="--psm 6"
        )
        return [
            line.strip()
            for line in text.splitlines()
            if len(line.strip()) > 3
        ]
    except Exception as e:
        print(f"OCR-fel: {e}")
        return []

# -----------------------------
# Restaurang-scrapers
# -----------------------------
def scrape_gastgivargarden():
    html = fetch_html("https://www.gastgivargarden.com/restaurang/dagens-lunch/")
    text = clean_soup_text(html)
    return extract_day_block(text, TODAY) if TODAY else []

def scrape_madame():
    html = fetch_html("https://madame.se/dagens-lunch/")
    text = clean_soup_text(html)
    return extract_day_block(text, TODAY) if TODAY else []

def scrape_vandalorum():
    url = "https://www.vandalorum.se/restaurang"
    html = fetch_html(url)
    soup = BeautifulSoup(html, "html.parser")

    items = soup.select("div.menu.w-dyn-item")
    if not items:
        return ["Kunde inte hitta lunchmeny."]

    lunch_items = []

    # Första blocket = Dagens lunch (tis–fre)
    first_menu = items[0]
    texts = first_menu.select("p.menu-text")

    for p in texts:
        text = p.get_text(strip=True)

        # STOPPVILLKOR
        if text.startswith("Inkl. sallad"):
            break

        # hoppa tomma rader
        if not text:
            continue

        lunch_items.append(text)

    if not lunch_items:
        return ["Ingen lunch hittades hos Vandalorum."]

    return lunch_items


def scrape_matkallaren():
    image_url = "https://matkallaren.nu/wp-content/uploads/meny-v-51.png"
    lines = ocr_image_from_url(image_url)

    if not lines:
        return ["Menyn publiceras som bild – kunde inte tolkas automatiskt."]

    if TODAY:
        joined = "\n".join(lines).lower()
        block = extract_day_block(joined, TODAY)
        return block if block else lines

    return lines

# -----------------------------
# Kör alla restauranger
# -----------------------------
data = {
    "Gästgivargården": scrape_gastgivargarden(),
    "Madame": scrape_madame(),
    "Vandalorum (veckomeny)": scrape_vandalorum(),
    "Matkällaren (OCR)": scrape_matkallaren()
}

# -----------------------------
# Generera HTML
# -----------------------------
html = f"""<!DOCTYPE html>
<html lang="sv">
<head>
<meta charset="UTF-8">
<title>Dagens lunch – {DATE_STR}</title>
<style>
body {{
    font-family: system-ui, Arial, sans-serif;
    background: #f5f5f5;
    padding: 2rem;
}}
h1 {{
    text-align: center;
}}
.card {{
    background: white;
    padding: 1.5rem;
    border-radius: 10px;
    margin-bottom: 1.2rem;
    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
}}
.empty {{
    color: #777;
    font-style: italic;
}}
</style>
</head>
<body>

<h1>Dagens lunch – {TODAY.capitalize() if TODAY else "Helg"}</h1>
"""

for name, items in data.items():
    html += f"<div class='card'><h2>{name}</h2>"
    if items:
        for item in items:
            html += f"<p>{item}</p>"
    else:
        html += "<p class='empty'>Ingen lunch publicerad.</p>"
    html += "</div>"

html += "</body></html>"

with open("dagens_lunch.html", "w", encoding="utf-8") as f:
    f.write(html)

print("✅ Slutgiltigt script klart – dagens_lunch.html skapad")
