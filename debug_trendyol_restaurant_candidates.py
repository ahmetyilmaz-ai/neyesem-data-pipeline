import json
from pathlib import Path


INPUT_DIR = Path("data/debug/trendyol_network")


def walk(obj):
    if isinstance(obj, dict):
        yield obj
        for value in obj.values():
            yield from walk(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from walk(item)


def main():
    files = sorted(INPUT_DIR.glob("*.json"))

    for file_path in files:
        with file_path.open("r", encoding="utf-8") as file:
            payload = json.load(file)

        url = payload.get("url", "")

        if "restaurants/filters" not in url:
            continue

        print("=" * 120)
        print(file_path.name)
        print(url)

        data = payload.get("data")

        count = 0

        for obj in walk(data):
            keys = {str(k).lower() for k in obj.keys()}

            # Muhtemel restoran objeleri
            has_name = any(k in keys for k in ["name", "title", "restaurantname", "displayname"])
            has_restaurant_signal = any(
                word in " ".join(keys)
                for word in ["restaurant", "store", "supplier", "merchant", "rating", "delivery", "kitchen", "cuisine"]
            )

            if has_name and has_restaurant_signal:
                count += 1
                print("\n--- Candidate", count, "---")
                for key, value in obj.items():
                    if isinstance(value, (str, int, float, bool)) or value is None:
                        print(f"{key}: {value}")

            if count >= 10:
                break


if __name__ == "__main__":
    main()
