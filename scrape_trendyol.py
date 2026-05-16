import json
from pathlib import Path

from playwright.sync_api import sync_playwright

from scrapers.trendyol_scraper import scrape_trendyol_url


URLS_PATH = Path("data/raw/trendyol_urls.txt")
OUTPUT_PATH = Path("data/raw/trendyol_raw.json")

MAX_RESTAURANTS = 20


def read_urls():
    urls = []

    with URLS_PATH.open("r", encoding="utf-8") as file:
        for line in file:
            line = line.strip().lstrip("\ufeff")

            if line and not line.startswith("#"):
                urls.append(line)

    return urls[:MAX_RESTAURANTS]


def save_results(results):
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_PATH.open("w", encoding="utf-8") as file:
        json.dump(results, file, ensure_ascii=False, indent=2)

    total_items = sum(len(r.get("items", [])) for r in results)

    print()
    print(f"Kaydedildi: {OUTPUT_PATH}")
    print(f"Restoran sayısı: {len(results)}")
    print(f"Toplam ürün: {total_items}")


def main():
    urls = read_urls()

    if not urls:
        raise ValueError("data/raw/trendyol_urls.txt içinde URL yok.")

    results = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        context = browser.new_context(
            viewport={"width": 1440, "height": 1000},
            locale="tr-TR",
        )
        page = context.new_page()

        try:
            for index, url in enumerate(urls, start=1):
                print()
                print(f"[{index}/{len(urls)}] İşleniyor: {url}")

                try:
                    result = scrape_trendyol_url(page, url)

                    if result and result.get("items"):
                        results.append(result)
                        save_results(results)
                    else:
                        print("Ürün bulunamadı, atlandı.")

                except Exception as exc:
                    print(f"Hata: {url} -> {exc}")

        except KeyboardInterrupt:
            print()
            print("İşlem kullanıcı tarafından durduruldu. Mevcut veriler kaydediliyor...")

        finally:
            save_results(results)
            browser.close()


if __name__ == "__main__":
    main()
