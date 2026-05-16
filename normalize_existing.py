import json
from pathlib import Path

from scrapers.yemeksepeti_normalizer import normalize_yemeksepeti_data


RAW_PATH = Path("data/raw/yemeksepeti_raw.json")
OUTPUT_PATH = Path("data/normalized/yemeksepeti_items.json")


def main():
    if not RAW_PATH.exists():
        raise FileNotFoundError(
            f"{RAW_PATH} bulunamadı. Önce scraped_restaurants_poc.json dosyasını "
            f"data/raw/yemeksepeti_raw.json olarak kopyala."
        )

    with RAW_PATH.open("r", encoding="utf-8") as file:
        raw_data = json.load(file)

    normalized_items = normalize_yemeksepeti_data(raw_data, city="bursa")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_PATH.open("w", encoding="utf-8") as file:
        json.dump(normalized_items, file, ensure_ascii=False, indent=2)

    print(f"{len(normalized_items)} ürün normalize edildi.")
    print(f"Çıktı: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()