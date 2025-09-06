# نصب کتابخانه‌ها (در GitHub Actions اجرا می‌شود)
# pip install pandas pandas_ta requests yfinance --quiet

import requests
import pandas as pd
import pandas_ta as ta
import sqlite3
import time

# مسیر دیتابیس در مخزن
db_path = "crypto_data_NEW1.db"
conn = sqlite3.connect(db_path)

# گرفتن لیست 100 ارز برتر
url = "https://api.coingecko.com/api/v3/coins/markets"
params = {"vs_currency": "usd", "order": "market_cap_desc", "per_page": 100, "page": 1}
response = requests.get(url, params=params)
top_symbols = [coin["id"] for coin in response.json()]

# محاسبه RSI
def calculate_rsi(data, window=14):
    delta = data['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

# دریافت داده‌ها و محاسبه اندیکاتورها
def fetch_data(symbol):
    url = f"https://api.coingecko.com/api/v3/coins/{symbol}/market_chart"
    params = {"vs_currency": "usd", "days": "30", "interval": "daily"}
    response = requests.get(url, params=params)
    if response.status_code != 200:
        print(f"❌ خطا در دریافت داده‌ها برای {symbol}")
        return None

    data = response.json()
    prices = data['prices']
    df = pd.DataFrame(prices, columns=["Open_Time", "Close"])
    df["Open_Time"] = pd.to_datetime(df["Open_Time"], unit="ms")
    df["Symbol"] = symbol
    df["Open"] = df["Close"].shift(1)
    df["High"] = df["Close"].rolling(2).max()
    df["Low"] = df["Close"].rolling(2).min()
    df["Volume"] = 0  # Volume صفر

    df = df.dropna()

    # اندیکاتورهای پایه
    df["RSI"] = calculate_rsi(df)
    df["SMA20"] = df["Close"].rolling(20).mean()
    df["EMA20"] = df["Close"].ewm(span=20, adjust=False).mean()
    df["MACD"] = df["EMA20"] - df["Close"].ewm(span=9, adjust=False).mean()
    df["Bollinger_Upper"] = df["SMA20"] + (df["Close"].rolling(20).std() * 2)
    df["Bollinger_Lower"] = df["SMA20"] - (df["Close"].rolling(20).std() * 2)

    df = df.sort_values("Open_Time").set_index("Open_Time")

    # شاخص‌های ترکیبی با try-except
    try:
        df["ATR"] = ta.atr(df["High"], df["Low"], df["Close"], length=14)
    except:
        df["ATR"] = None

    try:
        adx = ta.adx(df["High"], df["Low"], df["Close"], length=14)
        df["ADX"] = adx["ADX_14"]
    except:
        df["ADX"] = None

    try:
        stoch = ta.stoch(df["High"], df["Low"], df["Close"], k=14, d=3)
        df["Stochastic_K"] = stoch["STOCHk_14_3_3"]
        df["Stochastic_D"] = stoch["STOCHd_14_3_3"]
    except:
        df["Stochastic_K"] = None
        df["Stochastic_D"] = None

    try:
        df["VWAP"] = ta.vwap(df["High"], df["Low"], df["Close"], df["Volume"])
    except:
        df["VWAP"] = None

    df = df.reset_index()
    return df

# ایجاد جدول دیتابیس با PRIMARY KEY ترکیبی برای جلوگیری از داده تکراری
create_table = """
CREATE TABLE IF NOT EXISTS crypto_data_NEW1 (
    Symbol TEXT,
    Open_Time TEXT,
    Open REAL,
    High REAL,
    Low REAL,
    Close REAL,
    Volume REAL,
    RSI REAL,
    SMA20 REAL,
    EMA20 REAL,
    MACD REAL,
    Bollinger_Upper REAL,
    Bollinger_Lower REAL,
    ATR REAL,
    ADX REAL,
    Stochastic_K REAL,
    Stochastic_D REAL,
    VWAP REAL,
    PRIMARY KEY(Symbol, Open_Time)
);
"""
conn.execute(create_table)
conn.commit()

# دریافت و ذخیره داده‌ها بدون تکرار
for i, symbol in enumerate(top_symbols, start=1):
    print(f"⬇ ({i}/{len(top_symbols)}) دریافت داده برای {symbol} ...")
    df = fetch_data(symbol)
    if df is not None:
        if "EMA9" in df.columns:
            df = df.drop(columns=["EMA9"])
        try:
            df.to_sql("crypto_data_NEW1", conn, if_exists="append", index=False)
            print(f"✅ داده‌های {symbol} ذخیره شدند.")
        except sqlite3.IntegrityError:
            print(f"⚠ داده‌های {symbol} قبلاً وجود دارند، ذخیره نشد.")
    time.sleep(60)  # وقفه برای جلوگیری از بلاک شدن API

conn.close()
print("🎯 تمام داده‌ها ذخیره شدند.")
4