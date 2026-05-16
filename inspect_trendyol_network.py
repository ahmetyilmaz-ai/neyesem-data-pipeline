import json
from pathlib import Path


INPUT_DIR = Path("data/debug/trendyol_network")


KEYWORDS = [
    "product",
    "products",
    "menu",
    "menus",
    "item",
    "items",
    "price",
    "restaurant",
    "category",
    "categories",
    "name",
    "title",
]


def flatten_keys(obj, prefix=""):
    keys = []

    if isinstance(obj, dict):
        for key, value in obj.items():
            full_key = f"{prefix}.{key}" if prefix else str(key)
            keys.append(full_key)
            keys.extend(flatten_keys(value, full_key))

    elif isinstance(obj, list):
        for index, value in enumerate(obj[:5]):
            full_key = f"{prefix}[{index}]"
            keys.extend(flatten_keys(value, full_key))

    return keys


def contains_interesting_keys(keys):
    lower_keys = [key.lower() for key in keys]

    return any(
        keyword in key
        for keyword in KEYWORDS
        for key in lower_keys
    )


def main():
    if not INPUT_DIR.exists():
        raise FileNotFoundError(f"{INPUT_DIR} bulunamadı. Önce record_trendyol_network.py çalıştır.")

    files = sorted(INPUT_DIR.glob("*.json"))

    if not files:
        print("JSON response bulunamadı.")
        return

    print(f"{len(files)} JSON dosyası inceleniyor...\n")

    for file_path in files:
        with file_path.open("r", encoding="utf-8") as file:
            payload = json.load(file)

        url = payload.get("url")
        data = payload.get("data")

        keys = flatten_keys(data)

        if contains_interesting_keys(keys):
            print("=" * 100)
            print(file_path.name)
            print(url)
            print("Örnek key'ler:")

            for key in keys[:80]:
                print(f"  - {key}")

            print()

    print("İnceleme bitti.")


if __name__ == "__main__":
    main()
