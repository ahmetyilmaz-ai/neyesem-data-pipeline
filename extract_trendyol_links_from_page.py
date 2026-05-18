import argparse
import json
from pathlib import Path

from playwright.sync_api import sync_playwright


START_URL = "https://tgoyemek.com/restoranlar"
LOCATIONS_PATH = Path("data/config/locations.json")
OUTPUT_PATH = Path("data/raw/trendyol_urls.txt")


def load_location(name):
    with LOCATIONS_PATH.open("r", encoding="utf-8-sig") as file:
        locations = json.load(file)

    if name not in locations:
        available = ", ".join(locations.keys())
        raise ValueError(f"Bilinmeyen location: {name}. Kullanılabilir: {available}")

    return locations[name]


def normalize_url(href):
    if not href:
        return None

    href = href.strip()

    if href.startswith("http"):
        return href

    if href.startswith("/"):
        return f"https://tgoyemek.com{href}"

    return None


def extract_links(page):
    hrefs = page.locator("a").evaluate_all(
        """
        links => links
            .map(a => a.getAttribute('href'))
            .filter(Boolean)
        """
    )

    urls = []

    for href in hrefs:
        url = normalize_url(href)

        if not url:
            continue

        if "/restoranlar/" not in url:
            continue

        if url not in urls:
            urls.append(url)

    return urls


def scroll_page(page, rounds=12):
    for _ in range(rounds):
        page.mouse.wheel(0, 1800)
        page.wait_for_timeout(1000)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--location", default="bursa")
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()

    location = load_location(args.location)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)

        context = browser.new_context(
            viewport={"width": 1440, "height": 1000},
            locale="tr-TR",
            geolocation={
                "latitude": location["latitude"],
                "longitude": location["longitude"],
            },
            permissions=["geolocation"],
        )

        page = context.new_page()

        print(f"Sayfa açılıyor: {START_URL}")
        print(f"Konum: {args.location} ({location['latitude']}, {location['longitude']})")

        page.goto(START_URL, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(5000)

        scroll_page(page)

        urls = extract_links(page)

        if not urls:
            print("Link bulunamadı. Cookie/konum ekranı varsa tarayıcıda hallet.")
            input("Restoran listesi görününce Enter'a bas: ")
            scroll_page(page)
            urls = extract_links(page)

        urls = urls[:args.limit]

        with OUTPUT_PATH.open("w", encoding="utf-8") as file:
            for url in urls:
                file.write(url + "\n")

        print(f"{len(urls)} restoran linki bulundu.")
        print(f"Çıktı: {OUTPUT_PATH}")

        for url in urls[:20]:
            print("-", url)

        browser.close()


if __name__ == "__main__":
    main()

