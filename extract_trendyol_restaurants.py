import json
from pathlib import Path


INPUT_DIR = Path("data/debug/trendyol_network")
OUTPUT_JSON = Path("data/raw/trendyol_restaurants.json")
OUTPUT_URLS = Path("data/raw/trendyol_urls.txt")


ID_KEYS = {
    "id",
    "restaurantId",
    "restaurant_id",
    "storeId",
    "supplierId",
    "merchantId",
}

NAME_KEYS = {
    "name",
    "title",
    "restaurantName",
    "displayName",
}

URL_KEYS = {
    "url",
    "webUrl",
    "restaurantUrl",
    "seoUrl",
    "deeplink",
}


def walk(obj):
    if isinstance(obj, dict):
        yield obj
        for value in obj.values():
            yield from walk(value)

    elif isinstance(obj, list):
        for item in obj:
            yield from walk(item)


def pick_value(obj, keys):
    lower_map = {str(k).lower(): v for k, v in obj.items()}

    for key in keys:
        value = lower_map.get(key.lower())
        if value:
            return value

    return None


def normalize_url(value, restaurant_id):
    if not value:
        return None

    value = str(value)

    if value.startswith("http"):
        return value

    if value.startswith("/"):
        return f"https://tgoyemek.com{value}"

    if "restoranlar/" in value:
        return f"https://tgoyemek.com/{value.lstrip('/')}"

    return None


def main():
    restaurants = {}

    files = sorted(INPUT_DIR.glob("*.json"))

    for file_path in files:
        with file_path.open("r", encoding="utf-8") as file:
            payload = json.load(file)

        url = payload.get("url", "")

        if "restaurants/filters" not in url:
            continue

        data = payload.get("data")

        for obj in walk(data):
            restaurant_id = pick_value(obj, ID_KEYS)
            name = pick_value(obj, NAME_KEYS)
            raw_url = pick_value(obj, URL_KEYS)

            if not restaurant_id or not name:
                continue

            restaurant_id = str(restaurant_id)
            name = str(name).strip()

            if len(name) < 2 or len(name) > 120:
                continue

            restaurants[restaurant_id] = {
                "id": restaurant_id,
                "name": name,
                "url": normalize_url(raw_url, restaurant_id),
            }

    result = list(restaurants.values())

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_JSON.open("w", encoding="utf-8") as file:
        json.dump(result, file, ensure_ascii=False, indent=2)

    with OUTPUT_URLS.open("w", encoding="utf-8") as file:
        for restaurant in result[:20]:
            if restaurant.get("url"):
                file.write(restaurant["url"] + "\n")

    print(f"{len(result)} restoran bulundu.")
    print(f"JSON çıktı: {OUTPUT_JSON}")
    print(f"İlk 20 restoran URL dosyasına yazıldı: {OUTPUT_URLS}")

    for restaurant in result[:10]:
        print(f"- {restaurant['id']} | {restaurant['name']} | {restaurant['url']}")


if __name__ == "__main__":
    main()
