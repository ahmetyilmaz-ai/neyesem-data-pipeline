import json
from pathlib import Path
from playwright.sync_api import sync_playwright


URLS_PATH = Path("data/raw/trendyol_urls.txt")
OUTPUT_DIR = Path("data/debug/trendyol_menu_json")


KEYWORDS = [
    "product",
    "products",
    "menu",
    "menus",
    "category",
    "categories",
    "item",
    "items",
    "price",
    "name",
    "title",
    "restaurant",
]


def read_first_url():
    with URLS_PATH.open("r", encoding="utf-8-sig") as file:
        for line in file:
            line = line.strip()
            if line:
                return line

    raise ValueError("trendyol_urls.txt içinde URL yok.")


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


def walk(obj):
    if isinstance(obj, dict):
        yield obj
        for value in obj.values():
            yield from walk(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from walk(item)


def flatten_keys(obj, prefix=""):
    keys = []

    if isinstance(obj, dict):
        for key, value in obj.items():
            full_key = f"{prefix}.{key}" if prefix else str(key)
            keys.append(full_key)
            keys.extend(flatten_keys(value, full_key))

    elif isinstance(obj, list):
        for index, value in enumerate(obj[:3]):
            keys.extend(flatten_keys(value, f"{prefix}[{index}]"))

    return keys


def looks_interesting(data):
    keys = flatten_keys(data)
    lower = " ".join(keys).lower()

    return any(keyword in lower for keyword in KEYWORDS)


def count_name_price_objects(data):
    count = 0
    samples = []

    for obj in walk(data):
        if not isinstance(obj, dict):
            continue

        keys = {str(k).lower() for k in obj.keys()}

        has_name = any(k in keys for k in ["name", "title", "productname", "displayname"])
        has_price = any(
            "price" in k or k in ["amount", "value"]
            for k in keys
        )

        if has_name and has_price:
            count += 1

            if len(samples) < 5:
                samples.append({
                    key: value
                    for key, value in obj.items()
                    if isinstance(value, (str, int, float, bool)) or value is None
                })

    return count, samples


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    url = read_first_url()
    saved = 0

    print(f"Debug için açılıyor: {url}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            viewport={"width": 1440, "height": 1000},
            locale="tr-TR",
        )
        page = context.new_page()

        def on_response(response):
            nonlocal saved

            response_url = response.url
            content_type = response.headers.get("content-type", "")

            if "application/json" not in content_type:
                return

            if "tgoyemek" not in response_url and "tgoapis" not in response_url:
                return

            try:
                data = response.json()
            except Exception:
                return

            saved += 1

            payload = {
                "url": response_url,
                "status": response.status,
                "data": data,
            }

            file_path = OUTPUT_DIR / safe_filename(saved, response_url)

            with file_path.open("w", encoding="utf-8") as file:
                json.dump(payload, file, ensure_ascii=False, indent=2)

            interesting = looks_interesting(data)
            candidate_count, samples = count_name_price_objects(data)

            print()
            print("=" * 100)
            print(f"[{saved}] {response.status} {response_url}")
            print(f"interesting={interesting} candidate_name_price_objects={candidate_count}")

            if samples:
                print("Örnek objeler:")
                for sample in samples:
                    print(sample)

        page.on("response", on_response)

        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(5000)

        for _ in range(8):
            page.mouse.wheel(0, 1600)
            page.wait_for_timeout(1200)

        input("Sayfayı biraz kontrol et. Bitirmek için Enter: ")

        print()
        print(f"Toplam {saved} JSON response kaydedildi.")
        print(f"Klasör: {OUTPUT_DIR}")

        browser.close()


if __name__ == "__main__":
    main()
