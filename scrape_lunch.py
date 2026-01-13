import requests
import re
from bs4 import BeautifulSoup
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
    text = clean_soup_text(html)
    return extract_day_block(text, TODAY) if TODAY else []

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
:root {{
  --bg: #faf7f2;
  --card-bg: #fffdf9;
  --accent: #9b5c3c;
  --accent-soft: #ead7c5;
  --text: #2f2a26;
  --muted: #6f665f;
  --border: #e6ddd3;
}}

* {{
  box-sizing: border-box;
}}

body {{
  margin: 0;
  padding: 32px 16px;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI",
               Roboto, Oxygen, Ubuntu, Cantarell,
               "Helvetica Neue", Arial, sans-serif;
  background: linear-gradient(180deg, #faf7f2 0%, #f1ece5 100%);
  color: var(--text);
}}

h1 {{
  text-align: center;
  font-size: 2.2rem;
  margin-bottom: 40px;
  font-weight: 600;
  letter-spacing: 0.3px;
  color: #3a2f28;
}}

.container {{
  max-width: 900px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 28px;
}}

.restaurant {{
  background: var(--card-bg);
  border-radius: 16px;
  padding: 22px 26px 26px;
  border: 1px solid var(--border);
  box-shadow:
    0 8px 20px rgba(0, 0, 0, 0.06),
    inset 0 1px 0 rgba(255, 255, 255, 0.6);
}}

.restaurant h2 {{
  margin: 0 0 14px 0;
  font-size: 1.45rem;
  font-weight: 600;
  color: var(--accent);
  padding-bottom: 8px;
  border-bottom: 1px solid var(--accent-soft);
}}

.restaurant ul {{
  list-style: disc;
  padding-left: 22px;
  margin: 12px 0 0;
}}

.restaurant li {{
  margin-bottom: 10px;
  line-height: 1.5;
}}

.restaurant li::marker {{
  color: var(--accent);
}}

.restaurant p {{
  margin: 8px 0 0;
  color: var(--muted);
  font-style: italic;
}}

.menu-image {{
  margin-top: 14px;
  border-radius: 12px;
  max-width: 100%;
  border: 1px solid var(--border);
  background: #fff;
  box-shadow: 0 6px 14px rgba(0, 0, 0, 0.08);
}}

@media (max-width: 600px) {{
  body {{
    padding: 22px 12px;
  }}

  h1 {{
    font-size: 1.9rem;
    margin-bottom: 28px;
  }}

  .restaurant {{
    padding: 18px 20px 22px;
  }}
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
    html += "<p><em>Schnitzelfredag!!</em></p>"

if not matkallaren_image:
    html += "<p><h2>Menyn publiceras som bild – se matkallaren.nu</h2></p>"
html += "</div>"

html += "</body></html>"

with open("dagens_lunch.html", "w", encoding="utf-8") as f:
    f.write(html)

print("Dagens lunch genererad")
