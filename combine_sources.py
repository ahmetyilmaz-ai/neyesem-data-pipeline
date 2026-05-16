import json
from pathlib import Path


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

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_PATH.open("w", encoding="utf-8") as file:
        json.dump(all_items, file, ensure_ascii=False, indent=2)

    print(f"{len(all_items)} ürün birleştirildi.")
    print(f"Çıktı: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
