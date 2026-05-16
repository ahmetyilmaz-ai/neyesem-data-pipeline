from scrapers.utils import (
    parse_price,
    calculate_discount_rate,
    normalize_text,
    now_iso,
)


def normalize_yemeksepeti_restaurant(raw_restaurant, city="bursa"):
    """
    Mevcut scraper çıktısındaki tek restoranı standart ürün listesine çevirir.
    """

    restaurant_name = raw_restaurant.get("restoran_adi")
    restaurant_rating = raw_restaurant.get("puan")
    restaurant_url = raw_restaurant.get("url")

    normalized_items = []

    for raw_item in raw_restaurant.get("menu_urunleri", []):
        item_name = raw_item.get("isim")

        discounted_price = parse_price(raw_item.get("indirimli_fiyat"))
        original_price = parse_price(raw_item.get("indirimsiz_fiyat"))

        # Eğer indirimli fiyat yoksa güncel fiyat indirimsiz fiyattır
        price = discounted_price or original_price

        if not item_name or price is None:
            continue

        discount_rate = calculate_discount_rate(price, original_price)

        normalized_items.append(
            {
                "platform": "yemeksepeti",
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


def normalize_yemeksepeti_data(raw_data, city="bursa"):
    """
    Tüm Yemeksepeti raw datasını standart ürün listesine çevirir.
    """

    all_items = []

    for raw_restaurant in raw_data:
        items = normalize_yemeksepeti_restaurant(raw_restaurant, city=city)
        all_items.extend(items)

    return all_items