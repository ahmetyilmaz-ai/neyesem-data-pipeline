import json
from pathlib import Path

from scrapers.utils import normalize_text, calculate_discount_rate


RAW_PATH = Path("data/raw/getir_raw.json")
OUTPUT_PATH = Path("data/normalized/getir_items.json")


def main():
    if not RAW_PATH.exists():
        raise FileNotFoundError(f"{RAW_PATH} bulunamadı. Önce scrape_getir.py çalıştır.")

    with RAW_PATH.open("r", encoding="utf-8") as file:
        restaurants = json.load(file)

    normalized_items = []

    for restaurant in restaurants:
        restaurant_name = restaurant.get("restaurant_name")
        restaurant_rating = restaurant.get("restaurant_rating")
        restaurant_url = restaurant.get("restaurant_url")
        city = restaurant.get("city")
        scraped_at = restaurant.get("scraped_at")

        for item in restaurant.get("items", []):
            item_name = item.get("name")
            price = item.get("price")
            original_price = item.get("original_price") or price
            discount_rate = item.get("discount_percentage")

            if discount_rate is None:
                discount_rate = calculate_discount_rate(price, original_price)

            if not item_name or price is None:
                continue

            normalized_items.append(
                {
                    "platform": "getir_yemek",
                    "restaurant_name": restaurant_name,
                    "restaurant_rating": restaurant_rating,
                    "item_name": item_name,
                    "normalized_item_name": normalize_text(item_name),
                    "price": price,
                    "original_price": original_price,
                    "discount_rate": discount_rate,
                    "product_url": restaurant_url,
                    "city": city,
                    "scraped_at": scraped_at,
                }
            )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_PATH.open("w", encoding="utf-8") as file:
        json.dump(normalized_items, file, ensure_ascii=False, indent=2)

    print(f"{len(normalized_items)} Getir ürünü normalize edildi.")
    print(f"Çıktı: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
