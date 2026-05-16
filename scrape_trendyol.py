import json
from pathlib import Path

from scrapers.trendyol_scraper import scrape_trendyol_urls


URLS_PATH = Path("data/raw/trendyol_urls.txt")
OUTPUT_PATH = Path("data/raw/trendyol_raw.json")


def read_urls():
    if not URLS_PATH.exists():
        raise FileNotFoundError(f"{URLS_PATH} bulunamadı.")

    urls = []

    with URLS_PATH.open("r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()

            if not line or line.startswith("#"):
                continue

            urls.append(line)

    return urls


def main():
    urls = read_urls()

    if not urls:
        raise ValueError("trendyol_urls.txt içinde URL yok.")

    results = scrape_trendyol_urls(urls, headless=False)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_PATH.open("w", encoding="utf-8") as file:
        json.dump(results, file, ensure_ascii=False, indent=2)

    total_items = sum(len(restaurant.get("items", [])) for restaurant in results)

    print(f"{len(results)} restoran scrape edildi.")
    print(f"{total_items} ürün bulundu.")
    print(f"Çıktı: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()