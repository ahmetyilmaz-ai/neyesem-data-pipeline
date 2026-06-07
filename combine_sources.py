import json
from pathlib import Path

from scrapers.clean_and_enrich import clean_and_enrich


SOURCE_FILES = [
    Path("data/normalized/yemeksepeti_items.json"),
    Path("data/normalized/trendyol_items.json"),
    Path("data/normalized/getir_items.json"),
]

OUTPUT_PATH = Path("data/normalized/all_items.json")


def main():
    all_items = []

    for source_file in SOURCE_FILES:
        if not source_file.exists():
            print(f"Uyarı: {source_file} bulunamadı, atlanıyor.")
            continue

        with source_file.open("r", encoding="utf-8") as file:
            items = json.load(file)

        all_items.extend(items)
        print(f"{source_file}: {len(items)} ürün eklendi.")

    # Tek noktada temizlik + kategori + tekrar eleme.
    cleaned_items, stats = clean_and_enrich(all_items)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_PATH.open("w", encoding="utf-8") as file:
        json.dump(cleaned_items, file, ensure_ascii=False, indent=2)

    print()
    print("--- Temizlik özeti ---")
    print(f"Birleştirilen ham ürün : {stats['input']}")
    print(f"Elenen çöp kayıt       : {stats['dropped_garbage']}")
    print(f"Elenen birebir tekrar  : {stats['dropped_duplicate']}")
    print(f"Temiz ürün (çıktı)     : {stats['output']}")
    print(f"Çıktı: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
