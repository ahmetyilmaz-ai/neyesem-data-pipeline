import json
from pathlib import Path
from playwright.sync_api import sync_playwright


OUTPUT_DIR = Path("data/debug/trendyol_network")
START_URLS_PATH = Path("data/raw/trendyol_urls.txt")


def safe_filename(index, url):
    cleaned = (
        url.replace("https://", "")
        .replace("http://", "")
        .replace("/", "_")
        .replace("?", "_")
        .replace("&", "_")
        .replace("=", "_")
        .replace(":", "_")
    )
    return f"{index:03d}_{cleaned[:120]}.json"


def read_urls():
    urls = []

    with START_URLS_PATH.open("r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()

            if line and not line.startswith("#"):
                urls.append(line)

    return urls


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    urls = read_urls()

    if not urls:
        raise ValueError("data/raw/trendyol_urls.txt içinde URL yok.")

    saved_count = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            viewport={"width": 1440, "height": 1000},
            locale="tr-TR",
        )
        page = context.new_page()

        def on_response(response):
            nonlocal saved_count

            url = response.url
            content_type = response.headers.get("content-type", "")

            if "application/json" not in content_type:
                return

            try:
                data = response.json()
            except Exception:
                return

            saved_count += 1
            file_path = OUTPUT_DIR / safe_filename(saved_count, url)

            with file_path.open("w", encoding="utf-8") as file:
                json.dump(
                    {
                        "url": url,
                        "status": response.status,
                        "data": data,
                    },
                    file,
                    ensure_ascii=False,
                    indent=2,
                )

            print(f"[JSON] {response.status} {url}")

        page.on("response", on_response)

        for url in urls:
            print(f"\nSayfa açılıyor: {url}")
            page.goto(url, wait_until="domcontentloaded", timeout=60000)

            print("Cookie/konum ekranı varsa hallet.")
            print("Ürünler ekranda görününce Enter'a bas.")
            input("Hazır olunca Enter: ")

            for _ in range(8):
                page.mouse.wheel(0, 1800)
                page.wait_for_timeout(1200)

        print(f"\nToplam {saved_count} JSON response kaydedildi.")
        print(f"Klasör: {OUTPUT_DIR}")

        browser.close()


if __name__ == "__main__":
    main()
