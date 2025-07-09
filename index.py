from flask import Flask, request, jsonify
from flask_cors import CORS
import yfinance as yf
from yfinance.screener.screener import PREDEFINED_SCREENER_QUERIES, screen
from model.randomforest import predict_recommendation

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

@app.route("/download", methods=["GET"])
def download():
    ticker = request.args.get("ticker")
    start = request.args.get("start")
    end = request.args.get("end")
    if not ticker:
        return jsonify({"error": "ticker parameter required"}), 400
    data = yf.download(ticker, start=start, end=end)
    if data is None or data.empty:
        return jsonify({"error": "No data found for the given parameters"}), 404
    return data.reset_index().to_json(orient="records")

@app.route("/info", methods=["GET"])
def info():
    ticker = request.args.get("ticker")
    if not ticker:
        return jsonify({"error": "ticker parameter required"}), 400
    t = yf.Ticker(ticker)
    return jsonify(t.info)

@app.route("/history", methods=["GET"])
def history():
    ticker = request.args.get("ticker")
    period = request.args.get("period", "1mo")
    interval = request.args.get("interval", "1d")
    if not ticker:
        return jsonify({"error": "ticker parameter required"}), 400
    t = yf.Ticker(ticker)
    data = t.history(period=period, interval=interval)
    return data.reset_index().to_json(orient="records")

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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)