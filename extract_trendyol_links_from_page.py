from pathlib import Path
from playwright.sync_api import sync_playwright


START_URL = "https://tgoyemek.com/restoranlar"
OUTPUT_PATH = Path("data/raw/trendyol_urls.txt")


def normalize_url(href):
    if not href:
        return None

    href = href.strip()

    if href.startswith("http"):
        return href

    if href.startswith("/"):
        return f"https://tgoyemek.com{href}"

    return None


def main():
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    urls = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            viewport={"width": 1440, "height": 1000},
            locale="tr-TR",
        )
        page = context.new_page()

        print(f"Sayfa açılıyor: {START_URL}")
        page.goto(START_URL, wait_until="domcontentloaded", timeout=60000)

        print("Cookie/konum varsa hallet.")
        print("Restoran listesi görünene kadar bekle.")
        input("Hazır olunca Enter: ")

        for _ in range(12):
            page.mouse.wheel(0, 1800)
            page.wait_for_timeout(1000)

        hrefs = page.locator("a").evaluate_all(
            """
            links => links
                .map(a => a.getAttribute('href'))
                .filter(Boolean)
            """
        )

        for href in hrefs:
            url = normalize_url(href)

            if not url:
                continue

            if "/restoranlar/" not in url:
                continue

            if url not in urls:
                urls.append(url)

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
