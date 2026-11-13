#!/usr/bin/env python3
"""
Download Historical EOD Data of All NSE Indices
Fetches historical 'ind_close_all_DDMMYYYY.csv' files from the official NSE archives,
extracts valuation multiples (P/E, P/B, Dividend Yield, Close) for all major indices,
and can save raw CSVs or update valuation_data.json.
"""

import os
import sys
import io
import json
import argparse
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
import requests

IST = timezone(timedelta(hours=5, minutes=30))
DATA_FILE = "valuation_data.json"

NSE_INDEX_MAP = {
    "Nifty 50": "nifty50",
    "Nifty Midcap 150": "midcap150",
    "Nifty Smallcap 250": "smallcap250",
    "Nifty Bank": "bank",
    "Nifty IT": "it",
    "Nifty Pharma": "pharma",
    "Nifty FMCG": "fmcg",
    "Nifty Auto": "auto",
    "Nifty Metal": "metal",
    "Nifty Energy": "energy",
    "Nifty Realty": "realty",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Referer": "https://www.nseindia.com/",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
}

def clean_float(val, default=0.0):
    if val is None:
        return default
    s = str(val).replace(",", "").strip()
    if s in ["", "-", "nan", "None", "null"]:
        return default
    try:
        return float(s)
    except ValueError:
        return default

def download_single_date(dt: datetime, save_raw_dir=None):
    date_str = dt.strftime("%d%m%Y")
    iso_date = dt.strftime("%Y-%m-%d")
    url = f"https://archives.nseindia.com/content/indices/ind_close_all_{date_str}.csv"
    
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        if resp.status_code != 200 or len(resp.text.strip()) < 100:
            return iso_date, None, False

        # Optionally save raw CSV
        if save_raw_dir:
            os.makedirs(save_raw_dir, exist_ok=True)
            raw_path = os.path.join(save_raw_dir, f"ind_close_all_{date_str}.csv")
            with open(raw_path, "w", encoding="utf-8") as f:
                f.write(resp.text)

        df = pd.read_csv(io.StringIO(resp.text))
        df.columns = [c.strip() for c in df.columns]

        updates = {}
        for _, row in df.iterrows():
            idx_name = str(row.get("Index Name", "")).strip()
            if idx_name in NSE_INDEX_MAP:
                key = NSE_INDEX_MAP[idx_name]
                pe = clean_float(row.get("P/E"))
                pb = clean_float(row.get("P/B"))
                dy = clean_float(row.get("Div Yield"))
                close = clean_float(row.get("Closing Index Value"))

                if close > 0:
                    updates[key] = {
                        "date": iso_date,
                        "pe": round(pe, 2),
                        "pb": round(pb, 2),
                        "dy": round(dy, 2),
                        "close": round(close, 2),
                    }
        return iso_date, updates, True
    except Exception as e:
        return iso_date, None, False

def run_download(start_date: datetime, end_date: datetime, workers=10, save_raw_dir=None, export_csv=False):
    print(f"=== NSE Historical Valuation Downloader ===")
    print(f"Date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    print(f"Concurrent workers: {workers}")
    if save_raw_dir:
        print(f"Saving raw daily CSVs to: {save_raw_dir}")
    print("=" * 43)

    # Generate dates list
    curr = start_date
    date_list = []
    while curr <= end_date:
        # Skip Saturday (5) and Sunday (6)
        if curr.weekday() < 5:
            date_list.append(curr)
        curr += timedelta(days=1)

    print(f"Total potential trading days to query: {len(date_list)}")

    # Load existing database
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            db = json.load(f)
    else:
        db = {"last_updated": "", "indices": {}}

    found_count = 0
    total_data_points = 0
    all_rows = []

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(download_single_date, dt, save_raw_dir): dt for dt in date_list}
        for future in as_completed(futures):
            iso_date, updates, success = future.result()
            if success and updates:
                found_count += 1
                for key, record in updates.items():
                    series = db["indices"].setdefault(key, [])
                    # Deduplicate
                    idx = next((i for i, item in enumerate(series) if item["date"] == record["date"]), None)
                    if idx is not None:
                        series[idx] = record
                    else:
                        series.append(record)
                    total_data_points += 1
                    
                    if export_csv:
                        all_rows.append({
                            "Date": record["date"],
                            "Index": key,
                            "P/E": record["pe"],
                            "P/B": record["pb"],
                            "Div_Yield": record["dy"],
                            "Close": record["close"]
                        })
                print(f"  [OK] {iso_date} - {len(updates)} indices downloaded")
            else:
                pass

    # Sort each series chronologically
    for key in db.get("indices", {}):
        db["indices"][key].sort(key=lambda x: x["date"])

    db["last_updated"] = datetime.now(IST).isoformat()
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2)

    print("\n" + "=" * 43)
    print(f"Download complete! Successfully processed {found_count} trading sessions.")
    print(f"Saved to '{DATA_FILE}'. Total index series: {len(db['indices'])}")

    if export_csv and all_rows:
        df_all = pd.DataFrame(all_rows)
        df_all.sort_values(by=["Date", "Index"], inplace=True)
        csv_file = "all_indices_historical.csv"
        df_all.to_csv(csv_file, index=False)
        print(f"Consolidated CSV written to '{csv_file}' ({len(df_all)} rows)")

def main():
    parser = argparse.ArgumentParser(description="Download Historical NSE EOD Index Valuation Multiples")
    parser.add_argument("--days", type=int, default=180, help="Number of past days to download (default: 180)")
    parser.add_argument("--start", type=str, default=None, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, default=None, help="End date (YYYY-MM-DD)")
    parser.add_argument("--workers", type=int, default=10, help="Parallel worker threads (default: 10)")
    parser.add_argument("--save-raw", type=str, default=None, help="Directory to save raw ind_close_all_*.csv files")
    parser.add_argument("--export-csv", action="store_true", help="Also export a consolidated all_indices_historical.csv")

    args = parser.parse_args()

    now_ist = datetime.now(IST)
    if args.start:
        start_date = datetime.strptime(args.start, "%Y-%m-%d")
        end_date = datetime.strptime(args.end, "%Y-%m-%d") if args.end else now_ist
    else:
        end_date = now_ist
        start_date = now_ist - timedelta(days=args.days)

    run_download(start_date, end_date, workers=args.workers, save_raw_dir=args.save_raw, export_csv=args.export_csv)

if __name__ == "__main__":
    main()
