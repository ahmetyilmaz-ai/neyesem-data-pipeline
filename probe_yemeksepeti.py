"""
Yemeksepeti (Delivery Hero) API erişilebilirlik probu.

Amaç: senin makinenden Yemeksepeti/Delivery Hero veri API'lerine erişilip
erişilemediğini ve hangi endpoint'in ürün/restoran döndürdüğünü tespit etmek.
Trendyol'da yaptığımız "API avı"nın Yemeksepeti versiyonu.

Çalıştır:
    python probe_yemeksepeti.py
Sonra TÜM çıktıyı paylaş.
"""

import json
import urllib.request
import urllib.error

LAT, LON = 40.195, 29.060  # Bursa

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

# Delivery Hero web/app'in kullandığı bilinen header'lar.
BASE_HEADERS = {
    "User-Agent": UA,
    "Accept": "application/json",
    "Accept-Language": "tr-TR,tr;q=0.9",
    "x-fp-api-key": "volo",
    "Origin": "https://www.yemeksepeti.com",
    "Referer": "https://www.yemeksepeti.com/",
}

VENDOR_PARAMS = (
    f"latitude={LAT}&longitude={LON}&language_id=2&country=tr"
    "&configuration=Variant1&include=characteristics&customer_type=regular"
)

CANDIDATES = [
    # (açıklama, url, ekstra_header_gerekli_mi)
    ("DH vendors (tr.fd-api, api-key)", f"https://tr.fd-api.com/api/v5/vendors?{VENDOR_PARAMS}", True),
    ("DH vendors (api-key yok)",        f"https://tr.fd-api.com/api/v5/vendors?{VENDOR_PARAMS}", False),
    ("YS api host vendors",             f"https://api.yemeksepeti.com/api/v5/vendors?{VENDOR_PARAMS}", True),
    ("YS web /api proxy",               f"https://www.yemeksepeti.com/api/v5/vendors?{VENDOR_PARAMS}", True),
    ("DH disco",                        f"https://disco.deliveryhero.io/listing/api/v1/pandora/vendors?{VENDOR_PARAMS}", True),
]


def fetch(url, use_key):
    headers = dict(BASE_HEADERS)
    if not use_key:
        headers.pop("x-fp-api-key", None)
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:
        return "ERR", str(e).encode()


def summarize(body):
    try:
        d = json.loads(body)
    except Exception:
        head = body[:120].decode("utf-8", "replace")
        return f"(JSON değil) {head!r}"
    # vendor listesi var mı?
    def find_vendor_list(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k.lower() in ("items", "vendors", "organic_listing", "returned_count") and isinstance(v, list) and v:
                    return v
            for v in o.values():
                r = find_vendor_list(v)
                if r:
                    return r
        elif isinstance(o, list) and o and isinstance(o[0], dict):
            return o
        return None
    vlist = find_vendor_list(d)
    if vlist:
        sample = vlist[0]
        code = sample.get("code") or sample.get("id") or sample.get("vendor_code")
        name = sample.get("name") or sample.get("title")
        return f"VENDOR LIST! {len(vlist)} restoran | örnek code={code} name={name}"
    return f"json ama vendor listesi bulunamadı | top keys: {list(d.keys())[:8]}"


def main():
    print("Yemeksepeti / Delivery Hero API probu (Bursa)\n" + "=" * 55)
    for desc, url, use_key in CANDIDATES:
        status, body = fetch(url, use_key)
        line = f"[{str(status):>4}] {desc}"
        if isinstance(status, int) and status == 200:
            line += "  -> " + summarize(body)
        elif isinstance(status, int) and status == 403:
            line += "  -> 403 (büyük ihtimalle PerimeterX/bot koruması)"
        else:
            line += f"  -> {body[:80].decode('utf-8','replace')!r}"
        print(line)
    print("=" * 55)
    print("Bu çıktının tamamını paylaş.")


if __name__ == "__main__":
    main()
