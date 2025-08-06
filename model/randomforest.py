import os
import logging
import pandas as pd
import yfinance as yf
from ta.momentum import RSIIndicator
from ta.trend import MACD
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
import joblib

from yfinance import utils

# Set up root logger to ensure output to stdout
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format='%(asctime)s %(levelname)s %(message)s')

def get_model_path(interval):
    return os.path.join(os.path.dirname(__file__), f'rf_model_{interval}.joblib')

LABELS = {0: 'Sell', 1: 'Hold', 2: 'Buy'}

def fetch_features(ticker, interval='1d'):
    t = yf.Ticker(ticker)
    if interval == '1d':
        period = '1y'
        sma_period = 50
        ema_period = 50
    else:
        period = '1mo'
        sma_period = 20
        ema_period = 20
    df = t.history(period=period, interval=interval).copy()
    logger = utils.get_yf_logger()
    logger.info(f"DEBUG: history count for {ticker} ({interval}): {len(df)}")

    if df is None or df.empty or len(df) < 10:
        return None
    df = df.reset_index()
    if 'Date' not in df.columns:
        df['Date'] = df.index
    cols_needed = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume']
    for col in cols_needed:
        if col not in df.columns:
            raise ValueError(f"Column {col} not found in DataFrame")
    # Ensure close is always a pd.Series
    close = pd.Series(df['Close'])
    df['rsi'] = RSIIndicator(close).rsi()
    macd = MACD(close)
    df['macd'] = macd.macd()
    df['macd_signal'] = macd.macd_signal()
    df[f'sma_{sma_period}'] = close.rolling(window=sma_period).mean()
    df[f'ema_{ema_period}'] = close.ewm(span=ema_period, adjust=False).mean()
    df = df.dropna()
    return df

def label_data(df):
    # Simple labeling: if tomorrow's close > today's close: Buy, < Sell, else Hold
    df['target'] = 1  # Hold by default
    df.loc[df['Close'].shift(-1) > df['Close'], 'target'] = 2  # Buy
    df.loc[df['Close'].shift(-1) < df['Close'], 'target'] = 0  # Sell
    df = df.iloc[:-1]  # Remove last row (no future data)
    return df

def train_model(ticker='AAPL', interval='1d'):
    df = fetch_features(ticker, interval)
    if df is None:
        return None
    df = label_data(df)
    if df is None or len(df) < 5:
        return None
    sma_col = [col for col in df.columns if col.startswith('sma_')][0]
    ema_col = [col for col in df.columns if col.startswith('ema_')][0]
    X = df[['Close', 'rsi', 'macd', 'macd_signal', sma_col, ema_col]]
    y = df['target']
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    clf = RandomForestClassifier(n_estimators=100, random_state=42)
    clf.fit(X_train, y_train)
    joblib.dump(clf, get_model_path(interval))
    return clf

def load_or_train_model(interval='1d'):
    model_path = get_model_path(interval)
    if os.path.exists(model_path):
        return joblib.load(model_path)
    else:
        return train_model(interval=interval)

def predict_recommendation(ticker, interval='1d'):
    import numpy as np
    model = load_or_train_model(interval)
    df = fetch_features(ticker, interval)
    if df is None or len(df) == 0:
        return None
    sma_col = [col for col in df.columns if col.startswith('sma_')][0]
    ema_col = [col for col in df.columns if col.startswith('ema_')][0]
    X = df[['Close', 'rsi', 'macd', 'macd_signal', sma_col, ema_col]].tail(1)
    prediction = model.predict(X)[0] if model is not None else None
    # Convert prediction to int if it's a numpy type
    if prediction is not None and hasattr(prediction, 'item'):
        prediction = prediction.item()
    elif isinstance(prediction, int):
        prediction = int(prediction)
    confidence = None
    if model is not None and hasattr(model, "predict_proba"):
        proba = model.predict_proba(X)[0]
        confidence = float(max(proba))
    model_name = "RandomForest" if model is not None else None
    # Convert all input features to native Python types
    def to_serializable(val):
        if isinstance(val, int):
            return int(val)
        if isinstance(val, float):
            return float(val)
        return val
    input_features = {k: to_serializable(v) for k, v in X.iloc[0].to_dict().items()}
    if prediction is not None and prediction in LABELS:
        predicted_label = LABELS[prediction]
    else:
        predicted_label = 'Hold'
    from datetime import datetime, timezone
    timestamp = int(datetime.now(timezone.utc).timestamp() * 1000)
    return {
        "modelName": model_name,
        "inputFeatures": input_features,
        "predictedAction": predicted_label,
        "confidenceScore": confidence,
        "interval": interval,
        "timestamp": timestamp
    }
