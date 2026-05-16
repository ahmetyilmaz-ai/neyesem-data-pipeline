import json
import sys
from pathlib import Path

from scrapers.utils import normalize_text


DATA_PATH = Path("data/normalized/all_items.json")


def load_items():
    if not DATA_PATH.exists():
        raise FileNotFoundError(
            f"{DATA_PATH} bulunamadı. Önce combine_sources.py çalıştır."
        )

    with DATA_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def search_items(items, query):
    normalized_query = normalize_text(query)

    results = []

    for item in items:
        item_name = item.get("normalized_item_name", "")
        restaurant_name = normalize_text(item.get("restaurant_name", ""))

        if normalized_query in item_name or normalized_query in restaurant_name:
            results.append(item)

    return sorted(results, key=lambda item: item.get("price") or 999999)


def print_results(results):
    if not results:
        print("Sonuç bulunamadı.")
        return

    print()
    print(f"{'Platform':<15} {'Restoran':<25} {'Ürün':<35} {'Fiyat':>10} {'Eski Fiyat':>12} {'İndirim':>10}")
    print("-" * 115)

    for item in results:
        platform = item.get("platform", "-")
        restaurant = item.get("restaurant_name", "-")[:24]
        name = item.get("item_name", "-")[:34]
        price = item.get("price")
        original_price = item.get("original_price")
        discount_rate = item.get("discount_rate")

        price_text = f"{price:.2f} TL" if price is not None else "-"
        original_text = f"{original_price:.2f} TL" if original_price is not None else "-"
        discount_text = f"%{discount_rate:.1f}" if discount_rate is not None else "-"

        print(
            f"{platform:<15} {restaurant:<25} {name:<35} "
            f"{price_text:>10} {original_text:>12} {discount_text:>10}"
        )


def main():
    query = " ".join(sys.argv[1:]).strip()

    if not query:
        query = input("Aranacak yemek/restoran: ").strip()

    items = load_items()
    results = search_items(items, query)

    print_results(results)


if __name__ == "__main__":
    main()