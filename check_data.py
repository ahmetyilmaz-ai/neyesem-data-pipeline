import json
from collections import Counter

with open("data/normalized/all_items.json", encoding="utf-8") as f:
    items = json.load(f)

print("Toplam ürün:", len(items))
print("Platformlar:", Counter(i.get("platform") for i in items))
print("Restoranlar:", Counter(i.get("restaurant_name") for i in items).most_common(10))
print("İndirimler:", Counter(i.get("discount_rate") for i in items).most_common(10))
