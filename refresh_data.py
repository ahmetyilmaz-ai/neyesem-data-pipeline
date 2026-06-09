import argparse
import subprocess
import sys
from datetime import datetime


def run_step(title, command):
    print()
    print("=" * 80)
    print(title)
    print("=" * 80)
    print(" ".join(command))

    result = subprocess.run(command)

    if result.returncode != 0:
        raise RuntimeError(f"Adım başarısız oldu: {title}")


def main():
    parser = argparse.ArgumentParser(description="NeYesem veri yenileme pipeline (Trendyol API + Getir)")
    parser.add_argument(
        "--skip-scrape",
        action="store_true",
        help="Scrape işlemini atla, sadece normalize/combine yap",
    )
    args = parser.parse_args()

    python = sys.executable

    print(f"NeYesem data refresh başladı: {datetime.now().isoformat(timespec='seconds')}")

    if not args.skip_scrape:
        run_step(
            "Getir Yemek verisini çek (resmi API)",
            [python, "scrape_getir.py"],
        )

        run_step(
            "Trendyol Go verisini çek (resmi API)",
            [python, "scrape_trendyol_api.py", "--max", "0"],
        )

    run_step(
        "Trendyol verisini normalize et",
        [python, "normalize_trendyol.py"],
    )

    run_step(
        "Getir verisini normalize et",
        [python, "normalize_getir.py"],
    )

    run_step(
        "Tüm kaynakları birleştir (+ temizlik & kategori)",
        [python, "combine_sources.py"],
    )

    run_step(
        "Veri durumunu kontrol et",
        [python, "check_data.py"],
    )

    print()
    print("Veri yenileme tamamlandı.")
    print("Ana çıktı: data/normalized/all_items.json")


if __name__ == "__main__":
    main()
