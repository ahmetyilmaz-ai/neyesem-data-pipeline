import json
from pathlib import Path
from collections import Counter


def load_json(path):
    path = Path(path)
    if not path.exists():
        print(f"YOK: {path}")
        return None

    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


print("=== Trendyol URL listesi ===")
url_path = Path("data/raw/trendyol_urls.txt")
if url_path.exists():
    urls = [x.strip() for x in url_path.read_text(encoding="utf-8").splitlines() if x.strip()]
    print("URL sayısı:", len(urls))
    print("İlk 5:", urls[:5])
else:
    print("trendyol_urls.txt yok")

print("\n=== Trendyol raw ===")
trendyol = load_json("data/raw/trendyol_raw.json")
if trendyol is not None:
    print("Restoran sayısı:", len(trendyol))
    print("Toplam ürün:", sum(len(r.get("items", [])) for r in trendyol))
    for r in trendyol[:3]:
        print("-", r.get("restaurant_name"), "ürün:", len(r.get("items", [])))

print("\n=== Getir raw ===")
getir = load_json("data/raw/getir_raw.json")
if getir is not None:
    print("Restoran sayısı:", len(getir))
    print("Toplam ürün:", sum(len(r.get("items", [])) for r in getir))
    for r in getir[:3]:
        print("-", r.get("restaurant_name"), "ürün:", len(r.get("items", [])))

print("\n=== Normalized all ===")
all_items = load_json("data/normalized/all_items.json")
if all_items is not None:
    print("Toplam ürün:", len(all_items))
    print("Platformlar:", Counter(i.get("platform") for i in all_items))
