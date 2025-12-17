from playwright.sync_api import sync_playwright
from datetime import datetime

# -----------------------------
# Datum / rubrik
# -----------------------------
today_str = datetime.now().strftime("%Y-%m-%d")

# -----------------------------
# Scrapers (en per restaurang)
# -----------------------------
def scrape_gastgivargarden(page):
    page.goto("https://www.gastgivargarden.com/restaurang/dagens-lunch/", timeout=30000)
    page.wait_for_timeout(3000)

    items = []
    for p in page.locator("div.entry-content p").all():
        txt = p.inner_text().strip()
        if (
            len(txt) > 15
            and "lunch" not in txt.lower()
            and "pris" not in txt.lower()
        ):
            items.append(txt)

    return items


def scrape_madame(page):
    page.goto("https://madame.se/dagens-lunch/", timeout=30000)
    page.wait_for_timeout(3000)

    items = []
    for li in page.locator("section li").all():
        txt = li.inner_text().strip()
        if len(txt) > 5:
            items.append(txt)

    return items


def scrape_matkallaren(page):
    page.goto("https://matkallaren.nu/meny/", timeout=30000)
    page.wait_for_timeout(3000)

    items = []
    for el in page.locator(".menu-item, .meny-item, article, section").all():
        txt = el.inner_text().strip()
        if (
            len(txt) > 10
            and "öppettider" not in txt.lower()
            and "kontakt" not in txt.lower()
        ):
            items.append(txt)

    return items


def scrape_vandalorum(page):
    page.goto("https://www.vandalorum.se/restaurang", timeout=30000)
    page.wait_for_timeout(3000)

    items = []
    block = page.locator("p:has-text('Dagens lunch')")
    if block.count() > 0:
        items.append(block.first.inner_text().strip())

        next_el = block.first.locator("xpath=following-sibling::*[1]")
        if next_el.count() > 0:
            items.append(next_el.first.inner_text().strip())

    return items


# -----------------------------
# Kör allt
# -----------------------------
data = {}

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    data["Gästgivargården"] = scrape_gastgivargarden(page)
    data["Madame"] = scrape_madame(page)
    data["Matkällaren"] = scrape_matkallaren(page)
    data["Vandalorum"] = scrape_vandalorum(page)

    browser.close()

# -----------------------------
# Generera HTML
# -----------------------------
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
.empty {{
    color: #777;
    font-style: italic;
}}
</style>
</head>
<body>

<h1>Dagens lunch – {today_str}</h1>
<div class="container">
"""

for name, items in data.items():
    html += f"<div class='card'><h2>{name}</h2>"

    if items:
        for item in items:
            html += f"<p>{item}</p>"
    else:
        html += "<p class='empty'>Ingen lunch hittades.</p>"

    html += "</div>"

html += """
</div>
</body>
</html>
"""

with open("dagens_lunch.html", "w", encoding="utf-8") as f:
    f.write(html)

print("✅ Klar – komplett Playwright-script kördes")
