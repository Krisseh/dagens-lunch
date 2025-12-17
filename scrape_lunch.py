from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from datetime import datetime
import time

# -----------------------------
# Veckodag (svenska)
# -----------------------------
weekday_map = {
    0: "måndag",
    1: "tisdag",
    2: "onsdag",
    3: "torsdag",
    4: "fredag"
}

today = weekday_map.get(datetime.now().weekday())

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
# Hämta renderad HTML
# -----------------------------
def get_rendered_soup(page, url):
    page.goto(url, timeout=30000)
    page.wait_for_timeout(3000)  # låt JS ladda
    html = page.content()
    return BeautifulSoup(html, "html.parser")


# -----------------------------
# Scrapers (nu FUNKAR de)
# -----------------------------
def scrape_by_weekday(soup):
    """Generisk: hitta dagens veckodag och ta efterföljande rader"""
    results = []
    if not soup or not today:
        return results

    capture = False
    for el in soup.find_all(["p", "div", "li"]):
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


def scrape_vandalorum(soup):
    results = []
    for p in soup.find_all("p"):
        txt = p.get_text(" ", strip=True).lower()
        if "dagens lunch" in txt:
            results.append(p.get_text(strip=True))
            nxt = p.find_next_sibling("p")
            if nxt:
                results.append(nxt.get_text(strip=True))
    return results


scrapers = {
    "Gästgivargården": scrape_by_weekday,
    "Madame": scrape_by_weekday,
    "Matkällaren": scrape_by_weekday,
    "Vandalorum": scrape_vandalorum
}

# -----------------------------
# Kör Playwright
# -----------------------------
data = {}

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    for r in restaurants:
        print(f"Skrapar {r['name']}...")
        soup = get_rendered_soup(page, r["url"])
        data[r["name"]] = scrapers[r["name"]](soup)

    browser.close()

# -----------------------------
# HTML
# -----------------------------
today_str = datetime.now().strftime("%Y-%m-%d")

html = f"""<!DOCTYPE html>
<html lang="sv">
<head>
<meta charset="UTF-8">
<title>Dagens lunch – {today_str}</title>
<style>
body {{ font-family: Arial; background:#f3f3f3; }}
.container {{ max-width:900px; margin:auto; }}
.card {{ background:white; padding:20px; margin:20px 0; border-radius:8px; }}
.empty {{ color:#777; font-style:italic; }}
</style>
</head>
<body>
<h1 style="text-align:center;">Dagens lunch – {today}</h1>
<div class="container">
"""

for name, items in data.items():
    html += f"<div class='card'><h2>{name}</h2>"
    if items:
        for i in items:
            html += f"<p>{i}</p>"
    else:
        html += "<p class='empty'>Ingen lunch hittades.</p>"
    html += "</div>"

html += "</div></body></html>"

with open("dagens_lunch.html", "w", encoding="utf-8") as f:
    f.write(html)

print("✅ Klar – Playwright-version")
