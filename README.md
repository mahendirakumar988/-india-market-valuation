# IndiaMarketValuation 🇮🇳📈

> **Zero-Cost, Fully Automated Indian Market Valuation Dashboard & Daily Pipeline**  
> Tracks EOD P/E, P/B, and Dividend Yield multiples across 11+ NSE indices and BSE Sensex with automatic daily GitHub Actions syncing and GitHub Pages hosting.

---

## 🌟 Architecture Overview

Because web browsers enforce Cross-Origin Resource Sharing (CORS) rules that block direct client-side requests to NSE (`archives.nseindia.com`) and BSE (`bseindia.com`), this solution bypasses CORS without expensive paid proxy servers:

```
[NSE Daily EOD Archive (ind_close_all_DDMMYYYY.csv)]
                   │
                   ▼ (Every Mon-Fri @ 6:30 PM IST / 13:00 UTC)
    [GitHub Actions Runner (update_valuations.py)]
                   │
                   ▼ (Deduplicates & appends new session multiples)
     [valuation_data.json committed back to repo]
                   │
                   ▼ (GitHub Pages static CDN hosting)
   [IndiaMarketValuation Web App (index.html)]
   └── Client Auto-Sync Engine compares cached vs live dates
   └── Renders interactive valuation zones, charts & tables
```

---

## 🚀 Features

- **Live Auto-Sync Engine:** Automatically detects and merges new daily closing session multiples on page load with zero manual intervention.
- **Configurable JSON Feed:** Supports local `./valuation_data.json` or custom GitHub raw URLs.
- **Immediate "Sync Now" Trigger:** One-click re-fetch with live progress indicators.
- **Valuation Zone Indicator:** Visual gauge and percentile rank (Deep Value / Fair Value / Elevated / Euphoria) compared against 10-year historical percentiles.
- **Interactive Multi-Metric Charts:** Switch dynamically between P/E Multiple (with historical mean/median lines), P/B Ratio, Dividend Yield, Index Price, and Combined Valuation.
- **Historical Data Downloader:** Includes turnkey scripts to backfill years of daily trading sessions in parallel from official NSE archives.
- **Data Export:** Instant 1-click download of filtered index CSVs or the full valuation JSON database.

---

## 📁 Repository Structure

```text
├── index.html                           # Modern, responsive analytics web app
├── valuation_data.json                  # Database of historical & daily valuation multiples
├── update_valuations.py                 # Daily automated scraper for GitHub Actions
├── download_history.py                  # High-speed parallel historical backfiller
├── requirements.txt                     # Python dependencies (requests, pandas)
├── .github/
│   └── workflows/
│       └── daily_update.yml             # Scheduled GitHub Actions cron pipeline
└── README.md                            # Documentation and deployment walkthrough
```

---

## 🛠️ Step-by-Step Deployment Walkthrough

### Step 1: Preview Locally
To test the web app and live data locally on your computer:
```bash
python -m http.server 8000
```
Open [http://localhost:8000](http://localhost:8000) in your browser.

---

### Step 2: Push to a GitHub Repository
1. Initialize git and commit all files:
   ```bash
   git add .
   git commit -m "feat: complete automated IndiaMarketValuation dashboard and daily pipeline"
   ```
2. Create a new repository on [GitHub](https://github.com/new) (e.g. `india-market-valuation`).
3. Link and push to your GitHub repo:
   ```bash
   git remote add origin https://github.com/<YOUR_USERNAME>/india-market-valuation.git
   git branch -M main
   git push -u origin main
   ```

---

### Step 3: Grant GitHub Actions Write Permissions (Crucial ⚠️)
In order for GitHub Actions to commit updated `valuation_data.json` files back to your repository:
1. Go to your GitHub repository **Settings**.
2. Click **Actions** &rarr; **General** in the left sidebar.
3. Scroll down to **Workflow permissions**.
4. Select **"Read and write permissions"** and check **"Allow GitHub Actions to create and approve pull requests"**.
5. Click **Save**.

---

### Step 4: Enable GitHub Pages (Free Hosting)
1. Go to your GitHub repository **Settings**.
2. Click **Pages** in the left sidebar.
3. Under **Build and deployment** &rarr; **Source**, select **"Deploy from a branch"**.
4. Set the branch to **`main`** and folder to **`/(root)`**, then click **Save**.
5. Within 1–2 minutes, your live website will be accessible at:
   `https://<YOUR_USERNAME>.github.io/india-market-valuation/`

---

## 🔄 Daily Automation Schedule

The workflow `.github/workflows/daily_update.yml` runs automatically:
- **Cron:** `0 13 * * 1-5` (13:00 UTC = **6:30 PM IST**, Monday through Friday).
- NSE publishes its consolidated `ind_close_all_DDMMYYYY.csv` archives shortly after 6:00 PM IST on each trading day.
- You can also manually trigger a sync anytime from the **Actions** tab on GitHub using the **"Run workflow"** button (`workflow_dispatch`).

---

## 📚 Downloading Historical EOD Data of All NSE Indices

NSE archives all daily index files at:
`https://archives.nseindia.com/content/indices/ind_close_all_DDMMYYYY.csv`

### 1. Backfill Recent History (e.g. past 180 days)
```bash
python update_valuations.py --backfill 180
```

### 2. Full Multi-Year Historical Download with CSV Export
```bash
# Download 1 full year of historical trading sessions:
python download_history.py --days 365 --export-csv

# Or specify custom date ranges:
python download_history.py --start 2024-01-01 --end 2026-11-13 --workers 12 --export-csv
```
This generates `all_indices_historical.csv` and updates `valuation_data.json` with all past dates.
