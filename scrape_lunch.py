import requests
from bs4 import BeautifulSoup
from datetime import datetime

# -----------------------------
# Datum & veckodag (svenska)
# -----------------------------
weekday_map = {
    0: "måndag",
    1: "tisdag",
    2: "onsdag",
    3: "torsdag",
    4: "fredag"
}

today_index = datetime.now().weekday()
today = weekday_map.get(today_index)

# -----------------------------
# Restauranger
# -----------------------------
restaurants = [
    {
        "name": "Gästgivargården",
        "url": "https://www.gastgivargarden.com/restaurang/dagens-lunch/"
    },
    {
        "name": "Madame",
        "url": "https://madame.se/dagens-lunch/"
    },
    {
        "name": "Matkällaren",
        "url": "https://matkallaren.nu/meny/"
    },
    {
        "name": "Vandalorum",
        "url": "https://www.vandalorum.se/restaurang"
    }
]

# -----------------------------
# Hjälpfunktion
# -----------------------------
def fetch_soup(url):
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        return BeautifulSoup(r.text, "html.parser")
    except Exception as e:
        print(f"Fel vid hämtning av {url}: {e}")
        return None


# -----------------------------
# Scrapers
# -----------------------------
def scrape_gastgivargarden(soup):
    results = []
    if not soup or not today:
        return results

    content = soup.find("div", class_="entry-content")
    if not content:
        return results

    capture = False
    for p in content.find_all("p"):
        txt = p.get_text(" ", strip=True).lower()

        if today in txt:
            capture = True
            continue

        if capture:
            if any(day in txt for day in weekday_map.values()):
                break
            results.append(p.get_text(strip=True))

    return results


def scrape_madame(soup):
    results = []
    if not soup or not today:
        return results

    elements = soup.find_all(["p", "h3", "strong"])
    capture = False

    for el in elements:
        txt = el.get_text(" ", strip=True).lower()

        if today in txt:
            capture = True
            continue

        if capture:
            if any(day in txt for day in weekday_map.values()):
                break
            clean = el.get_text(strip=True)
            if len(clean) > 3:
                results.append(clean)

    return results


def scrape_matkallaren(soup):
    results = []
    if not soup or not today:
        return results

    for el in soup.find_all(["p", "div"]):
        txt = el.get_text(" ", strip=True).lower()
        if today in txt:
            results.append(el.get_text(strip=True))

    return results


def scrape_vandalorum(soup):
    results = []
    if not soup:
        return results

    for p in soup.find_all("p"):
        txt = p.get_text(" ", strip=True).lower()

        if "dagens lunch" in txt:
            results.append(p.get_text(strip=True))

            nxt = p.find_next_sibling("p")
            if nxt:
                results.append(nxt.get_text(strip=True))

    return results


scrapers = {
    "Gästgivargården": scrape_gastgivargarden,
    "Madame": scrape_madame,
    "Matkällaren": scrape_matkallaren,
    "Vandalorum": scrape_vandalorum
}

# -----------------------------
# Kör scraping
# -----------------------------
data = {}

for r in restaurants:
    print(f"Skrapar {r['name']}...")
    soup = fetch_soup(r["url"])
    items = scrapers[r["name"]](soup)
    data[r["name"]] = items

# -----------------------------
# Generera HTML
# -----------------------------
today_str = datetime.now().strftime("%Y-%m-%d")

html = f"""<!DOCTYPE html>
<html lang="sv">
<head>
<meta charset="UTF-8">
<title>Dagens lunch – {today_str}</title>
<style>
body {{
    font-family: Arial, sans-serif;
    background: #f3f3f3;
}}
h1 {{
    text-align: center;
}}
.container {{
    max-width: 900px;
    margin: auto;
}}
.card {{
    background: white;
    padding: 20px;
    margin: 20px 0;
    border-radius: 8px;
    box-shadow: 0 2px 6px rgba(0,0,0,0.1);
}}
h2 {{
    margin-top: 0;
}}
p {{
    margin: 6px 0;
}}
.empty {{
    color: #777;
    font-style: italic;
}}
</style>
</head>
<body>

<h1>Dagens lunch – {today.capitalize() if today else today_str}</h1>
<div class="container">
"""

for name, items in data.items():
    html += f"<div class='card'><h2>{name}</h2>"

    if items:
        for item in items:
            html += f"<p>{item}</p>"
    else:
        html += "<p class='empty'>Ingen lunch publicerad för idag.</p>"

    html += "</div>"

html += """
</div>
</body>
</html>
"""

with open("dagens_lunch.html", "w", encoding="utf-8") as f:
    f.write(html)

print("✅ Klar – dagens_lunch.html uppdaterad")
