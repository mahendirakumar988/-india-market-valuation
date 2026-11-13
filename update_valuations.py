#!/usr/bin/env python3
"""
Daily Indian Index Valuation Sync
Scrapes NSE EOD index archives and BSE Sensex valuation ratios,
updating valuation_data.json automatically.
"""

from datetime import datetime, timedelta, timezone
import json
import os
import sys
import io
import argparse
from concurrent.futures import ThreadPoolExecutor
import pandas as pd
import requests

IST = timezone(timedelta(hours=5, minutes=30))
DATA_FILE = "valuation_data.json"

NSE_INDEX_MAP = {
    "Nifty 50": "nifty50",
    "Nifty Next 50": "next50",
    "Nifty 500": "nifty500",
    "Nifty Midcap 150": "midcap150",
    "Nifty Smallcap 250": "smallcap250",
    "Nifty Bank": "bank",
    "Nifty PSU Bank": "psubank",
    "Nifty IT": "it",
    "Nifty Pharma": "pharma",
    "Nifty FMCG": "fmcg",
    "Nifty Auto": "auto",
    "Nifty Infrastructure": "infra",
    "Nifty Metal": "metal",
    "Nifty Energy": "energy",
    "Nifty Realty": "realty",
}

def clean_float(val, default=0.0):
    """Safely converts string or numeric values to float, handling '-', commas and empty values."""
    if val is None:
        return default
    s = str(val).replace(",", "").strip()
    if s in ["", "-", "nan", "None", "null"]:
        return default
    try:
        return float(s)
    except ValueError:
        return default

def fetch_nse_eod(target_date: datetime):
    """
    Fetches daily NSE closing values, P/E, P/B, and Div Yield for all mapped indices
    from the official NSE archives (ind_close_all_DDMMYYYY.csv).
    """
    date_str = target_date.strftime("%d%m%Y")
    url = f"https://archives.nseindia.com/content/indices/ind_close_all_{date_str}.csv"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Referer": "https://www.nseindia.com/",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    }
    try:
        resp = requests.get(url, headers=headers, timeout=20)
        if resp.status_code != 200 or len(resp.text.strip()) < 100:
            return None

        df = pd.read_csv(io.StringIO(resp.text))
        df.columns = [c.strip() for c in df.columns]
        iso_date = target_date.strftime("%Y-%m-%d")

        updates = {}
        for _, row in df.iterrows():
            idx_name = str(row.get("Index Name", "")).strip()
            if idx_name in NSE_INDEX_MAP:
                key = NSE_INDEX_MAP[idx_name]
                try:
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
                except (ValueError, KeyError):
                    continue
        return updates
    except Exception as exc:
        print(f"Error fetching NSE archive for {date_str}: {exc}")
        return None

def fetch_bse_sensex(target_date: datetime):
    """Fetches latest BSE Sensex P/E, P/B, and Dividend Yield from BSE India API."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://www.bseindia.com/",
        "Accept": "application/json, text/plain, */*"
    }
    url = "https://api.bseindia.com/BseIndiaAPI/api/Sensex/w"
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list) and len(data) > 0:
                row = data[0]
                pe = clean_float(row.get("PE"))
                pb = clean_float(row.get("PB"))
                dy = clean_float(row.get("DivYield"))
                close = clean_float(row.get("ltp"))
                return {
                    "date": target_date.strftime("%Y-%m-%d"),
                    "pe": round(pe, 2),
                    "pb": round(pb, 2),
                    "dy": round(dy, 2),
                    "close": round(close, 2),
                }
    except Exception as exc:
        pass
    return None

def load_database():
    """Loads valuation_data.json or creates a new empty schema."""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning reading existing data file: {e}. Starting fresh.")
    return {"last_updated": "", "indices": {}}

def save_database(db):
    """Saves database to valuation_data.json sorted by date."""
    for key in db.get("indices", {}):
        db["indices"][key].sort(key=lambda x: x["date"])
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2)

def merge_record(db, key, record):
    """Merges a single daily record into the given index series without duplicates."""
    series = db["indices"].setdefault(key, [])
    for idx, item in enumerate(series):
        if item["date"] == record["date"]:
            series[idx] = record
            return False
    series.append(record)
    return True

def backfill_history(days=60, workers=8):
    """Backfills past historical trading days in parallel from NSE archives."""
    print(f"Backfilling past {days} days across {len(NSE_INDEX_MAP)} indices...")
    db = load_database()
    now_ist = datetime.now(IST)
    target_dates = [now_ist - timedelta(days=i) for i in range(days, 0, -1)]

    total_added = 0
    def worker(dt):
        return dt, fetch_nse_eod(dt)

    with ThreadPoolExecutor(max_workers=workers) as executor:
        for dt, updates in executor.map(worker, target_dates):
            if updates:
                for key, record in updates.items():
                    if merge_record(db, key, record):
                        total_added += 1

    db["last_updated"] = now_ist.isoformat()
    save_database(db)
    print(f"Backfill complete! Added/updated {total_added} data points across {len(db['indices'])} indices.")

def main():
    parser = argparse.ArgumentParser(description="Indian Index Valuation Sync Engine")
    parser.add_argument("--backfill", type=int, default=0, help="Number of past days to backfill historical data (e.g. 60 or 180)")
    parser.add_argument("--date", type=str, default=None, help="Target date in DD-MM-YYYY format")
    args = parser.parse_args()

    if args.backfill > 0:
        backfill_history(days=args.backfill)
        return

    now_ist = datetime.now(IST)
    if args.date:
        target_date = datetime.strptime(args.date, "%d-%m-%Y").replace(tzinfo=IST)
    else:
        target_date = now_ist

    print(f"Running valuation scraper for target date: {target_date.strftime('%Y-%m-%d')}")

    nse_updates = fetch_nse_eod(target_date)

    if not nse_updates and not args.date:
        for lookback in range(1, 8):
            cand_date = now_ist - timedelta(days=lookback)
            cand_updates = fetch_nse_eod(cand_date)
            if cand_updates:
                target_date = cand_date
                nse_updates = cand_updates
                break

    if not nse_updates:
        print("No NSE archive could be fetched. Exiting.")
        return

    db = load_database()

    for key, record in nse_updates.items():
        merge_record(db, key, record)

    sensex_record = fetch_bse_sensex(target_date)
    if sensex_record and sensex_record["pe"] > 0:
        merge_record(db, "sensex", sensex_record)

    db["last_updated"] = now_ist.isoformat()
    save_database(db)
    print(f"Successfully updated {len(nse_updates)} indices for {target_date.strftime('%Y-%m-%d')}")

if __name__ == "__main__":
    main()
