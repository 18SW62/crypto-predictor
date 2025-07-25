import requests
import pandas as pd
import pandas_ta as ta
import json
import ftplib
from datetime import datetime
import time

# === CONFIG ===
MIN_VOLUME_USDT = 100000
FTP_HOST = "ftpupload.net"
FTP_USER = "if0_39559718"
FTP_PASS = "00Xdt8LGUy"
FTP_DIR = "htdocs"

# === Get all USDT pairs ===
def get_usdt_pairs():
    url = "https://api.binance.com/api/v3/exchangeInfo"
    res = requests.get(url).json()
    symbols = []
    for s in res['symbols']:
        if s['quoteAsset'] == 'USDT' and s['status'] == 'TRADING':
            symbols.append(s['symbol'])
    return symbols

# === Get 24h volume ===
def get_24h_volume():
    url = "https://api.binance.com/api/v3/ticker/24hr"
    res = requests.get(url).json()
    volume_data = {item['symbol']: float(item['quoteVolume']) for item in res}
    return volume_data

# === Get OHLCV data ===
def get_ohlcv(symbol):
    url = f"https://api.binance.com/api/v3/klines"
    params = {"symbol": symbol, "interval": "15m", "limit": 100}
    try:
        res = requests.get(url, params=params)
        data = res.json()
        df = pd.DataFrame(data, columns=[
            "time", "open", "high", "low", "close", "volume",
            "close_time", "quote_asset_vol", "num_trades",
            "taker_base_vol", "taker_quote_vol", "ignore"
        ])
        df["close"] = pd.to_numeric(df["close"])
        df["volume"] = pd.to_numeric(df["volume"])
        return df
    except:
        return None

# === Analyze Signal ===
def analyze(df):
    if df is None or df.empty:
        return None
    df.ta.rsi(length=14, append=True)
    df.ta.macd(append=True)
    last_rsi = df["RSI_14"].iloc[-1]
    macd_hist = df["MACDh_12_26_9"].iloc[-1]
    volume_change = ((df["volume"].iloc[-1] - df["volume"].iloc[-2]) / df["volume"].iloc[-2]) * 100
    buy_price = df["close"].iloc[-1]

    if last_rsi < 30 and macd_hist > 0:
        risk = "LOW"
        confidence = "High"
        target = round(buy_price * 1.015, 4)
    elif last_rsi < 40:
        risk = "MEDIUM"
        confidence = "Medium"
        target = round(buy_price * 1.01, 4)
    elif last_rsi < 50:
        risk = "HIGH"
        confidence = "Low"
        target = round(buy_price * 1.007, 4)
    else:
        return None

    return {
        "buy_price": round(buy_price, 4),
        "target_price": target,
        "rsi": round(last_rsi, 2),
        "macd_hist": round(macd_hist, 5),
        "volume_change": round(volume_change, 2),
        "risk": risk,
        "confidence": confidence,
        "reason": f"RSI={round(last_rsi,2)}, MACD={round(macd_hist,4)}, VolΔ={round(volume_change,2)}%"
    }

# === Upload to InfinityFree ===
def upload_to_ftp(filename):
    try:
        with ftplib.FTP(FTP_HOST) as ftp:
            ftp.login(FTP_USER, FTP_PASS)
            ftp.cwd(FTP_DIR)
            with open(filename, "rb") as f:
                ftp.storbinary(f"STOR today_signal.json", f)
        print("✅ Uploaded to website")
    except Exception as e:
        print("❌ FTP Error:", e)

# === MAIN SCRIPT ===
usdt_pairs = get_usdt_pairs()
volume_data = get_24h_volume()

results = []
count = 0

for symbol in usdt_pairs:
    if volume_data.get(symbol, 0) < MIN_VOLUME_USDT:
        continue

    print(f"⏳ Analyzing {symbol}...")
    df = get_ohlcv(symbol)
    signal = analyze(df)

    if signal:
        results.append({"symbol": symbol, **signal})

    count += 1
    if count % 15 == 0:
        time.sleep(10)  # Avoid Binance rate limits

data = {
    "date": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    "recommendations": results
}

with open("today_signal.json", "w") as f:
    json.dump(data, f, indent=2)

upload_to_ftp("today_signal.json")
