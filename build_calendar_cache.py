import yfinance as yf
import pandas as pd
import requests
import json
from datetime import datetime
import time

CACHE_FILE = "calendar_cache.json"
SEC_TICKER_URL = "https://www.sec.gov/files/company_tickers.json"
USER_AGENT = {"User-Agent": "YourName your.email@example.com"}

def get_cik(ticker_symbol):
    """Fetch CIK for a given ticker using SEC’s public ticker-CIK mapping."""
    try:
        response = requests.get(SEC_TICKER_URL, headers=USER_AGENT)
        response.raise_for_status()
        ticker_data = response.json()
        for item in ticker_data.values():
            if item["ticker"].upper() == ticker_symbol.upper():
                return str(item["cik_str"]).zfill(10)
        return None
    except Exception as e:
        print(f"Error fetching CIK for {ticker_symbol}: {e}")
        return None

def get_ticker_filings(ticker_symbol):
    """Fetch recent 8-K filings for a specific ticker using SEC Submissions API."""
    try:
        cik = get_cik(ticker_symbol)
        if not cik:
            print(f"[get_ticker_filings] No CIK found for {ticker_symbol}")
            return []
        url = f"https://data.sec.gov/submissions/CIK{cik}.json"
        response = requests.get(url, headers=USER_AGENT)
        response.raise_for_status()
        filings = response.json()
        recent_filings = filings.get("filings", {}).get("recent", {})
        if recent_filings:
            forms = recent_filings.get("form", [])
            descriptions = recent_filings.get("description", [])
            filing_dates = recent_filings.get("filingDate", [])
            accession_numbers = recent_filings.get("accessionNumber", [])
            result = []
            for i, (form, date, acc_no) in enumerate(zip(forms, filing_dates, accession_numbers)):
                if form == "8-K":
                    desc = descriptions[i] if i < len(descriptions) else ""
                    result.append({
                        "ticker": ticker_symbol,
                        "cik": cik,
                        "description": desc,
                        "link": f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc_no.replace('-', '')}/{acc_no}.htm",
                        "date": date
                    })
            return result[:5]
        return []
    except Exception as e:
        print(f"Error fetching SEC filings for {ticker_symbol}: {e}")
        return []

def build_calendar_cache(limit=None):
    # Download SEC ticker list
    response = requests.get(SEC_TICKER_URL, headers=USER_AGENT)
    response.raise_for_status()
    tickers = [item["ticker"].upper() for item in response.json().values()]
    if limit:
        tickers = tickers[:limit]
    now = pd.Timestamp.now(tz='UTC')
    results = []
    total = len(tickers)
    for idx, tkr in enumerate(tickers, 1):
        try:
            ticker = yf.Ticker(tkr)
            cal = ticker.calendar
            # Prepare all calendar fields for this ticker
            cal_entry = {"ticker": tkr, "calendar": []}
            if isinstance(cal, pd.DataFrame) and not cal.empty:
                for field in cal.index:
                    val = cal.loc[field]
                    # Try to extract all values for this field
                    if hasattr(val, 'values'):
                        arr = pd.Series(val.values)
                        arr = arr[~pd.isnull(arr)]
                        for v in arr:
                            # Ensure v is a datetime and tz-aware if possible
                            try:
                                v_dt = pd.to_datetime(v)
                                if v_dt.tzinfo is None:
                                    v_dt = v_dt.tz_localize('UTC')
                                # Only add if in the future
                                if v_dt > now:
                                    v_str = str(v_dt)
                                    cal_entry["calendar"].append({"event": field, "date": v_str})
                            except Exception:
                                v_str = str(v)
                                cal_entry["calendar"].append({"event": field, "date": v_str})
                    else:
                        if not pd.isnull(val):
                            try:
                                v_dt = pd.to_datetime(val)
                                if v_dt.tzinfo is None:
                                    v_dt = v_dt.tz_localize('UTC')
                                if v_dt > now:
                                    v_str = str(v_dt)
                                    cal_entry["calendar"].append({"event": field, "date": v_str})
                            except Exception:
                                v_str = str(val)
                                cal_entry["calendar"].append({"event": field, "date": v_str})
            # Also try to get all future earnings dates from earnings_dates if available
            try:
                edf = getattr(ticker, 'earnings_dates', None)
                if edf is not None and not edf.empty:
                    for dt in edf.index:
                        # Ensure dt is timezone-aware (UTC)
                        dt_aware = pd.to_datetime(dt)
                        if dt_aware.tzinfo is None:
                            dt_aware = dt_aware.tz_localize('UTC')
                        if dt_aware > now:
                            cal_entry["calendar"].append({"event": "Earnings Date", "date": str(dt_aware)})
            except Exception:
                pass

            # Add recent 8-K filings as events
            try:
                filings = get_ticker_filings(tkr)
            
                for filing in filings:
                    # Ensure 8-K date is tz-aware and in the future
                    try:
                        filing_dt = pd.to_datetime(filing["date"])
                        if filing_dt.tzinfo is None:
                            filing_dt = filing_dt.tz_localize('UTC')

                        cal_entry["calendar"].append({
                            "event": "8-K",
                            "date": str(filing_dt),
                            "description": filing.get("description", ""),
                            "link": filing.get("link", "")
                        })
                    except Exception:
                        cal_entry["calendar"].append({
                            "event": "8-K",
                            "date": filing["date"],
                            "description": filing.get("description", ""),
                            "link": filing.get("link", "")
                        })
            except Exception as e:
                print(f"Error fetching 8-K filings for {tkr}: {e}")
            if cal_entry["calendar"]:
                # Sort calendar entries by date if possible
                def parse_date_safe(val):
                    try:
                        return pd.to_datetime(val["date"])
                    except Exception:
                        return pd.NaT
                cal_entry["calendar"].sort(key=parse_date_safe)
                results.append(cal_entry)
        except Exception as e:
            print(f"Error fetching calendar for {tkr}: {e}")
        print(f"Processed {idx}/{total} ({(idx/total)*100:.1f}%) - {tkr}")
    # Save to file
    with open(CACHE_FILE, "w") as f:
        json.dump({
            "results": results,
            "count": len(results),
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }, f, indent=2)
    print(f"Saved {len(results)} upcoming earnings to {CACHE_FILE}")

if __name__ == "__main__":
    build_calendar_cache()
