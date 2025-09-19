from flask import abort
from finvizfinance.quote import finvizfinance
from flask import Flask, request, jsonify
from flask_cors import CORS
from scrape_xstocks import check_cache
import scrape_xstocks
import yfinance as yf
from yfinance.screener.screener import PREDEFINED_SCREENER_QUERIES, screen
from model.randomforest import predict_recommendation

# Additional imports for catalyst detection

from bs4 import BeautifulSoup
import json
import os
from datetime import datetime, timedelta, timezone
from yfinance import Search

import requests
import numpy as np

# Define the cache file for earnings calendar
CACHE_FILE = "calendar_cache.json"

# Helper function to fetch 8-K filings for a specific ticker
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

@app.route("/price", methods=["GET"])
def price():
    ticker = request.args.get("ticker")
    if not ticker:
        return jsonify({"error": "ticker parameter required"}), 400
    try:
        t = yf.Ticker(ticker)
        price = t.fast_info.last_price
        volume = t.fast_info.last_volume
        return jsonify({"ticker": ticker, "price": price, "volume": volume})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/watchlist", methods=["GET"])
def watchlist():
    tickers_param = request.args.get("tickers")
    if not tickers_param:
        return jsonify({"error": "tickers parameter required"}), 400
    tickers_list = [t.strip() for t in tickers_param.split(",") if t.strip()]
    try:
        combined_query = " ".join(tickers_list)
        tickers_obj = yf.Tickers(combined_query)
        # Load xstocks cache
        try:
            xstock_tokens = check_cache() or []
            xstock_set = set(t['symbol'] for t in xstock_tokens if 'symbol' in t)
        except Exception:
            xstock_set = set()
        # Collect info for each ticker
        results = []
        for tkr in tickers_list:
            try:
                t = tickers_obj.tickers.get(tkr)
                if t is None:
                    results.append({"ticker": tkr, "error": "Not found in batch", "xstock": False})
                    continue
                fi = dict(t.info) if hasattr(t.info, 'items') else t.info.__dict__
                fi["ticker"] = tkr
                fi["xstock"] = (tkr + 'x') in xstock_set
                results.append(fi)
            except Exception as e:
                results.append({"ticker": tkr, "error": str(e), "xstock": False})
        creation_ts = int(datetime.now(timezone.utc).timestamp())
        return jsonify({"canonicalName": "WATCHLIST","count": len(results), "creationDate": creation_ts, "quotes": results})
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route("/info", methods=["GET"])
def info():
    ticker = request.args.get("ticker")
    tickers_param = request.args.get("tickers")
    if tickers_param:
        tickers_list = [t.strip() for t in tickers_param.split(",") if t.strip()]
        # Load xstocks cache
        try:
            xstock_tokens = check_cache() or []
            xstock_set = set(t['symbol'] for t in xstock_tokens if 'symbol' in t)
        except Exception:
            xstock_set = set()
        infos = []
        for tkr in tickers_list:
            try:
                t = yf.Ticker(tkr)
                info = t.info
                cal = t.calendar
                # Convert DataFrame to list of dicts if needed
                try:
                    import pandas as pd
                    if isinstance(cal, pd.DataFrame):
                        cal = cal.reset_index().to_dict(orient="records")
                except ImportError:
                    pass
                info["calendar"] = cal
                # Add news using finvizfinance
                try:
                    stock = finvizfinance(tkr.upper())
                    news_data = stock.ticker_news()
                    try:
                        import pandas as pd
                        if isinstance(news_data, pd.DataFrame):
                            news_data = news_data.to_dict(orient="records")
                    except ImportError:
                        pass
                    info["news"] = news_data
                except Exception as e:
                    info["news"] = {"error": str(e)}
            except Exception as e:
                info = {"error": str(e), "calendar": None, "news": None}
            info["ticker"] = tkr
            info["xstock"] = (tkr + 'x') in xstock_set
            infos.append(info)
        return jsonify(infos)
    if not ticker:
        return jsonify({"error": "ticker parameter required"}), 400
    # Load xstocks cache
    try:
        xstock_tokens = check_cache() or []
        xstock_set = set(t['symbol'] for t in xstock_tokens if 'symbol' in t)
    except Exception:
        xstock_set = set()
    t = yf.Ticker(ticker)
    info = t.info
    cal = t.calendar
    # Convert DataFrame to list of dicts if needed
    try:
        import pandas as pd
        if isinstance(cal, pd.DataFrame):
            cal = cal.reset_index().to_dict(orient="records")
    except ImportError:
        pass
    info["calendar"] = cal
    # Add news using finvizfinance
    try:
        stock = finvizfinance(ticker.upper())
        news_data = stock.ticker_news()
        try:
            import pandas as pd
            if isinstance(news_data, pd.DataFrame):
                news_data = news_data.to_dict(orient="records")
        except ImportError:
            pass
        info["news"] = news_data
    except Exception as e:
        info["news"] = {"error": str(e)}
    info["xstock"] = (ticker + 'x') in xstock_set
    return jsonify(info)

@app.route("/history", methods=["GET"])
def history():
    ticker = request.args.get("ticker")
    period = request.args.get("period", "1mo")
    interval = request.args.get("interval", "1d")
    start = request.args.get("start")
    if not start:
        start = None
    
    if not ticker:
        return jsonify({"error": "ticker parameter required"}), 400
    t = yf.Ticker(ticker)
    data = t.history(period=period, interval=interval, start=start)
    # Only keep the required columns and rename them
    compact = []
    import pandas as pd
    from datetime import datetime
    import pandas as pd
    for idx, row in data.iterrows():
        if isinstance(idx, (pd.Timestamp, datetime)):
            date_str = idx.strftime("%Y-%m-%dT%H:%M:%S")
        else:
            date_str = str(idx)
        compact.append({
            "D": date_str,
            "O": row["Open"],
            "H": row["High"],
            "L": row["Low"],
            "C": row["Close"],
            "V": row["Volume"]
        })
    chart_link = (
        f"https://charts2-node.finviz.com/chart.ashx?cs=l"
        f"&t={ticker.upper()}"
        f"&tf=d"
        f"&s=linear"
        f"&pm=0"
        f"&am=0"
        f"&ct=candle_stick"
        f"&o[0][ot]=sma&o[0][op]=20&o[0][oc]=FF8F33C6"
        f"&o[1][ot]=sma&o[1][op]=50&o[1][oc]=DCB3326D"
        f"&o[2][ot]=sma&o[2][op]=200&o[2][oc]=DC32B363"
        f"&o[3][ot]=patterns&o[3][op]=&o[3][oc]=000"
    )
    return jsonify({
        "history": compact,
        "chart_link": chart_link
    })

@app.route("/screener/run", methods=["GET"])
def run_screener():
    """
    Run a predefined screener query.
    Usage: /screener/run?query=day_gainers
    """
    query = request.args.get("query")
    if not query:
        return jsonify({"error": "query parameter required"}), 400
    if query not in PREDEFINED_SCREENER_QUERIES:
        return jsonify({"error": f"Unknown query '{query}'"}), 400
    try:
        result = screen(query)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/predict", methods=["GET"])
def predict():
    ticker = request.args.get("ticker")
    interval = request.args.get("interval", "1d")
    if not ticker:
        return jsonify({"error": "ticker parameter required"}), 400
    rec = predict_recommendation(ticker, interval)
    if rec is None:
        return jsonify({"error": "Could not generate prediction for ticker"}), 404
    return jsonify({"recommendation": rec, "interval": interval})

# Calendar endpoint for batch closest earnings
@app.route("/calendar", methods=["GET"])
def calendar():
    lookahead_days = int(request.args.get("nextdays", 30))  # Default 30 days
    start_offset_days = int(request.args.get("offsetdays", 1))  # Default 0 days offset
    cache_path = os.path.join(os.path.dirname(__file__), CACHE_FILE)
    try:
        print(f"[calendar] Using cache_path: {cache_path}")
        with open(cache_path, "r") as f:
            cache = json.load(f)
        all_results = cache.get("results")
        if len(all_results) == 0:
            return jsonify({"results": [], "count": 0, "last_updated": cache.get("last_updated")}), 200
        now = datetime.now(timezone.utc)
        ticker_events = {}
        print(f"[calendar] Found {len(all_results)} cached earnings entries.")

        for entry in all_results:
            ticker = entry.get("ticker")
            if not ticker:
                continue
            for cal in entry.get("calendar", []):
                cal_date = cal.get("date")
                cal_event = cal.get("event")
                # add description and link if available
                cal_description = cal.get("description", "")
                cal_link = cal.get("link", "")
                if not cal_date or not cal_event:
                    continue
                try:
                    event_date = datetime.fromisoformat(cal_date)
                except Exception:
                    continue
                if event_date >= now - timedelta(days=start_offset_days) and event_date <= now + timedelta(days=lookahead_days):
                    print(f"[calendar] Including: {ticker} | {cal_event} | {cal_date}")
                    if ticker not in ticker_events:
                        ticker_events[ticker] = []
                    ticker_events[ticker].append({"event": cal_event, "date": cal_date, "description": cal_description, "link": cal_link})
                else:
                    print(f"[calendar] Skipping: {ticker} | {cal_event} | {cal_date}")

        # Build results in the requested format
        results = []
        for ticker, events in ticker_events.items():
            results.append({"ticker": ticker, "calendar": events})

        if not results:
            return jsonify({"results": [], "count": 0, "last_updated": cache.get("last_updated")}), 200
        # Sort by soonest event date for each ticker
        results.sort(key=lambda x: min(datetime.fromisoformat(ev["date"]) for ev in x["calendar"]))
        response_data = {
            "results": results,
            "count": len(results),
            "last_updated": cache.get("last_updated")
        }
        return jsonify(response_data), 200
    except Exception as e:
        return jsonify({"error": f"Could not read earnings cache: {e}"}), 500

# Add a news endpoint using finvizfinance
@app.route("/news", methods=["GET"])
def news():
    ticker = request.args.get("ticker")
    if finvizfinance is None:
        return jsonify({"error": "finvizfinance package not installed"}), 500
    try:
        if ticker:
            stock = finvizfinance(ticker.upper())
            news_data = stock.ticker_news()
            # If news_data is a DataFrame, convert to list of dicts
            try:
                import pandas as pd
                if isinstance(news_data, pd.DataFrame):
                    news_data = news_data.to_dict(orient="records")
            except ImportError:
                pass
            return jsonify({"ticker": ticker.upper(), "news": news_data})
        else:
            # General market news
            from finvizfinance.news import News
            news = News()
            news_data = news.get_news()
            # If news_data is a DataFrame, convert to list of dicts
            try:
                import pandas as pd
                if isinstance(news_data, pd.DataFrame):
                    news_data = news_data.to_dict(orient="records")
            except ImportError:
                pass
            return jsonify({"news": news_data})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/xstocks', methods=["GET"])
def get_xstocks():
    try:
        symbol_query = request.args.get("symbol")
        tokens = check_cache()
        if not tokens:
            tokens = scrape_xstocks.scrape_xstocks()
        if not tokens:
            return jsonify({"error": "Failed to retrieve xStocks data"}), 500
        if symbol_query:
            filtered = [t for t in tokens if t.get("symbol", "").lower() == symbol_query.lower()]
            return jsonify({"tokens": filtered})
        return jsonify({"tokens": tokens})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Catch-all route for debugging 404s
@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Not found", "message": str(e), "path": request.path}), 404

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
