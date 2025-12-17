import requests
from bs4 import BeautifulSoup
from datetime import datetime
import re
from PIL import Image, ImageEnhance, ImageFilter
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
    r = requests.get(url, timeout=15)
    r.encoding = "utf-8"
    return r.text

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

        # 1. Gråskala
        #img = img.convert("L")

        # 2. Öka kontrast
        #enhancer = ImageEnhance.Contrast(img)
        #img = enhancer.enhance(2.5)

        # 3. Skärpa
        #img = img.filter(ImageFilter.SHARPEN)

        # 4. OCR
        text = pytesseract.image_to_string(
            img,
            lang="swe",
            config="--psm 6"
        )

        lines = [
            line.strip()
            for line in text.splitlines()
            if len(line.strip()) > 3
        ]

        return lines

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

    menu_divs = soup.select("div.menu-div")
    if not menu_divs:
        return ["Kunde inte hitta lunchmeny."]

    lunch_items = []

    for menu in menu_divs:
        texts = menu.select("p.menu-text")

        for p in texts:
            text = p.get_text(strip=True)

            # hoppa tomma
            if not text:
                continue

            # STOPPVILLKOR exakt som du vill ha
            if text.startswith("Inkl. sallad"):
                return lunch_items if lunch_items else ["Ingen lunch hittades."]

            # filtrera bort uppenbart icke-lunch
            if text.lower().startswith("à la carte"):
                continue

            lunch_items.append(text)

        # om vi hittat något rimligt → detta är rätt block
        if len(lunch_items) >= 2:
            return lunch_items

        # annars nollställ och testa nästa menu-div
        lunch_items = []

    return ["Ingen lunch hittades hos Vandalorum."]



def scrape_matkallaren():
    image_url = "https://matkallaren.nu/wp-content/uploads/sites/1341/2025/12/meny-v-51.png"
    lines = ocr_image_from_url(image_url)

    if not lines:
        return ["Menyn publiceras som bild – kunde inte tolkas automatiskt."]

    if TODAY:
        joined = "\n".join(lines)
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
