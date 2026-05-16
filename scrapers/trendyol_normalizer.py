from scrapers.utils import (
    parse_price,
    calculate_discount_rate,
    normalize_text,
    now_iso,
)


def normalize_trendyol_restaurant(raw_restaurant, city="bursa"):
    restaurant_name = raw_restaurant.get("restaurant_name")
    restaurant_rating = raw_restaurant.get("restaurant_rating")
    restaurant_url = raw_restaurant.get("restaurant_url")

    normalized_items = []

    for raw_item in raw_restaurant.get("items", []):
        item_name = raw_item.get("name")

        price = parse_price(raw_item.get("price"))
        original_price = parse_price(raw_item.get("original_price"))

        if not item_name or price is None:
            continue

        discount_rate = calculate_discount_rate(price, original_price)

        normalized_items.append(
            {
                "platform": "trendyol",
                "restaurant_name": restaurant_name,
                "restaurant_rating": restaurant_rating,
                "item_name": item_name,
                "normalized_item_name": normalize_text(item_name),
                "price": price,
                "original_price": original_price,
                "discount_rate": discount_rate,
                "product_url": restaurant_url,
                "city": city,
                "scraped_at": now_iso(),
            }
        )

    return normalized_items


def normalize_trendyol_data(raw_data, city="bursa"):
    all_items = []

    for raw_restaurant in raw_data:
        items = normalize_trendyol_restaurant(raw_restaurant, city=city)
        all_items.extend(items)

    return all_items