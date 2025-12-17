import requests
from bs4 import BeautifulSoup
from datetime import datetime

# Restauranger som ska skrapas
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

def fetch_soup(url):
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        return BeautifulSoup(r.text, "html.parser")
    except Exception as e:
        print(f"Fel vid hämtning av {url}: {e}")
        return None


def scrape_gastgivargarden(soup):
    results = []
    if soup:
        content = soup.find("div", class_="entry-content")
        if content:
            results = [
                p.get_text(strip=True)
                for p in content.find_all("p")
                if p.get_text(strip=True)
            ]
    return results


def scrape_madame(soup):
    results = []
    if soup:
        for el in soup.find_all(["h2", "h3", "p"]):
            txt = el.get_text(strip=True)
            if txt:
                results.append(txt)
    return results


def scrape_matkallaren(soup):
    results = []
    if soup:
        for p in soup.find_all("p"):
            txt = p.get_text(strip=True)
            if "dagens" in txt.lower() or "lunch" in txt.lower():
                results.append(txt)
    return results


def scrape_vandalorum(soup):
    results = []
    if soup:
        for p in soup.find_all("p"):
            txt = p.get_text(strip=True)
            if "lunch" in txt.lower():
                results.append(txt)
    return results


scrapers = {
    "Gästgivargården": scrape_gastgivargarden,
    "Madame": scrape_madame,
    "Matkällaren": scrape_matkallaren,
    "Vandalorum": scrape_vandalorum
}

# Samla data
data = {}

for r in restaurants:
    print(f"Skrapar {r['name']}...")
    soup = fetch_soup(r["url"])
    data[r["name"]] = scrapers[r["name"]](soup)

# Skapa HTML
today = datetime.now().strftime("%Y-%m-%d")

html = f"""<!DOCTYPE html>
<html lang="sv">
<head>
<meta charset="UTF-8">
<title>Dagens Lunch {today}</title>
<style>
body {{
    font-family: Arial, sans-serif;
    background: #f2f2f2;
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
    color: #333;
}}
p {{
    margin: 6px 0;
}}
</style>
</head>
<body>

<h1>Dagens Lunch – {today}</h1>
<div class="container">
"""

for name, items in data.items():
    html += f"<div class='card'><h2>{name}</h2>"
    if items:
        for item in items:
            html += f"<p>{item}</p>"
    else:
        html += "<p>Ingen lunchinformation hittades.</p>"
    html += "</div>"

html += """
</div>
</body>
</html>
"""

with open("dagens_lunch.html", "w", encoding="utf-8") as f:
    f.write(html)

print("✅ Klar! HTML skapad: dagens_lunch.html")
