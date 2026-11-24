import os
import requests
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from datetime import datetime, timezone, timedelta

# 設定中文字型（對應 GitHub Actions 安裝的 Noto Sans CJK）
plt.rcParams['font.sans-serif'] = ['Noto Sans CJK TC', 'Noto Sans CJK JP', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

TW_TZ = timezone(timedelta(hours=8))
NOW_STR = datetime.now(TW_TZ).strftime('%Y-%m-%d %H:%M')

def get_yf_quote(ticker):
    try:
        df = yf.Ticker(ticker).history(period="5d")
        if len(df) < 2:
            return None, None, None
        close = df['Close'].iloc[-1]
        prev = df['Close'].iloc[-2]
        chg = close - prev
        pct = (chg / prev) * 100
        return close, chg, pct
    except Exception:
        return None, None, None

def get_vix_5y():
    try:
        df = yf.Ticker("^VIX").history(period="5y")
        return df['Close']
    except Exception:
        return pd.Series(dtype=float)

def get_cnn_fear_greed():
    url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        r = requests.get(url, headers=headers, timeout=10).json()
        fg = r.get("fear_and_greed", {})
        return {
            "score": round(fg.get("score", 0), 1),
            "rating": fg.get("rating", "N/A").title(),
            "prev_close": round(fg.get("previous_close", 0), 1),
            "prev_1w": round(fg.get("previous_1_week", 0), 1),
        }
    except Exception:
        return None

def get_taifex_txf():
    """抓取期交所台指期最新報價"""
    url = "https://mis.taifex.com.tw/futures/api/getQuoteList"
    payload = {"MarketType": "1", "SymbolType": "F", "KindID": "1", "CID": "TXF", "ExpireMonth": "", "RowSize": "全部", "PageNo": "", "SortColumn": "", "AscDesc": "A"}
    try:
        r = requests.post(url, json=payload, timeout=10).json()
        quotes = r.get("RtData", {}).get("QuoteList", [])
        if quotes:
            q = quotes[0]
            return q.get("CLastPrice", "N/A"), q.get("CDiff", "0"), q.get("CDiffRate", "0%")
    except Exception:
        pass
    return None, None, None

def get_fed_implied_rate():
    """透過 30-Day Fed Funds Futures (ZQ=F) 估算市場隱含利率"""
    try:
        df = yf.Ticker("ZQ=F").history(period="5d")
        if not df.empty:
            price = df['Close'].iloc[-1]
            implied = 100.0 - price
            return round(price, 3), round(implied, 2)
    except Exception:
        pass
    return None, None

def build_dashboard(output_path="market_report.png"):
    fig = plt.figure(figsize=(14, 10), facecolor='#121212')
    gs = gridspec.GridSpec(3, 2, figure=fig, hspace=0.4, wspace=0.25)

    fig.suptitle(f"台股盤前 / 盤後 市場總覽儀表板  ({NOW_STR} CST)",
                 fontsize=18, fontweight='bold', color='white', y=0.97)

    # --- 1. 美股四大指數 ---
    ax1 = fig.add_subplot(gs[0, 0])
    ax1.set_facecolor('#1E1E1E')
    ax1.set_title("美股四大指數", color='white', fontsize=13, pad=10, fontweight='bold')
    ax1.axis('off')
    us_tickers = [("道瓊工業", "^DJI"), ("NASDAQ", "^IXIC"), ("S&P 500", "^GSPC"), ("費城半導體", "^SOX")]
    y_pos = 0.82
    for name, tk in us_tickers:
        val, chg, pct = get_yf_quote(tk)
        if val is not None:
            color = '#FF5252' if chg >= 0 else '#00E676'  # 台股習慣紅漲綠跌
            sign = "▲" if chg >= 0 else "▼"
            text = f"{name:<10}  {val:,.2f}   {sign} {abs(chg):,.2f} ({pct:+.2f}%)"
        else:
            color = '#AAAAAA'
            text = f"{name:<10}  暫無資料"
        ax1.text(0.05, y_pos, text, color=color, fontsize=11.5, fontweight='bold', transform=ax1.transAxes)
        y_pos -= 0.22

    # --- 2. 台股加權 & 台指期夜盤 ---
    ax2 = fig.add_subplot(gs[0, 1])
    ax2.set_facecolor('#1E1E1E')
    ax2.set_title("台股加權指數 & 台指期盤後", color='white', fontsize=13, pad=10, fontweight='bold')
    ax2.axis('off')
    tw_val, tw_chg, tw_pct = get_yf_quote("^TWII")
    if tw_val is not None:
        c = '#FF5252' if tw_chg >= 0 else '#00E676'
        ax2.text(0.05, 0.72, f"加權指數：{tw_val:,.2f} ({tw_pct:+.2f}%)", color=c, fontsize=12, fontweight='bold', transform=ax2.transAxes)
    else:
        ax2.text(0.05, 0.72, "加權指數：暫無資料", color='#AAAAAA', fontsize=12, transform=ax2.transAxes)

    txf_p, txf_chg, txf_pct = get_taifex_txf()
    if txf_p:
        ax2.text(0.05, 0.42, f"台指期盤後：{txf_p}  ({txf_chg} / {txf_pct})", color='#FFD54F', fontsize=12, fontweight='bold', transform=ax2.transAxes)
    else:
        ax2.text(0.05, 0.42, "台指期盤後：非夜盤時段或暫無資料", color='#AAAAAA', fontsize=11, transform=ax2.transAxes)

    ax2.text(0.05, 0.12, "※ 融資維持率請見證交所臺股儀表板（晚間更新）", color='#90CAF9', fontsize=9.5, transform=ax2.transAxes)

    # --- 3. CNN 恐懼與貪婪指數 ---
    ax3 = fig.add_subplot(gs[1, 0])
    ax3.set_facecolor('#1E1E1E')
    ax3.set_title("CNN Fear & Greed Index", color='white', fontsize=13, pad=10, fontweight='bold')
    fg = get_cnn_fear_greed()
    if fg:
        score = fg['score']
        bar_color = '#FF5252' if score < 25 else ('#FFA726' if score < 45 else ('#FFEE58' if score < 55 else '#00E676'))
        ax3.barh(['目前分數'], [score], color=bar_color, height=0.4)
        ax3.set_xlim(0, 100)
        ax3.tick_params(colors='white')
        ax3.text(score + 2 if score < 85 else score - 18, 0, f"{score} ({fg['rating']})",
                 va='center', color='white', fontsize=12, fontweight='bold')
        ax3.set_xlabel(f"前日: {fg['prev_close']}  |  一週前: {fg['prev_1w']}", color='#CCCCCC', fontsize=10)
    else:
        ax3.axis('off')
        ax3.text(0.5, 0.5, "暫無法取得 CNN 數據", color='#AAAAAA', ha='center', va='center')

    # --- 4. 美聯儲隱含利率 (Fed Funds Futures) ---
    ax4 = fig.add_subplot(gs[1, 1])
    ax4.set_facecolor('#1E1E1E')
    ax4.set_title("美聯儲利率期貨隱含水準 (ZQ=F)", color='white', fontsize=13, pad=10, fontweight='bold')
    ax4.axis('off')
    zq_price, implied = get_fed_implied_rate()
    if zq_price:
        ax4.text(0.05, 0.65, f"期貨價格：{zq_price}", color='white', fontsize=12, transform=ax4.transAxes)
        ax4.text(0.05, 0.35, f"市場隱含利率：約 {implied:.2f}%", color='#80CBC4', fontsize=14, fontweight='bold', transform=ax4.transAxes)
    else:
        ax4.text(0.05, 0.5, "暫無法取得利率期貨數據", color='#AAAAAA', fontsize=11, transform=ax4.transAxes)

    # --- 5. VIX 指數 5 年走勢 ---
    ax5 = fig.add_subplot(gs[2, :])
    ax5.set_facecolor('#1E1E1E')
    vix = get_vix_5y()
    if not vix.empty:
        latest_vix = vix.iloc[-1]
        ax5.plot(vix.index, vix.values, color='#66BB6A', linewidth=1.5)
        ax5.fill_between(vix.index, vix.values, color='#66BB6A', alpha=0.15)
        ax5.axhline(20, color='#FFA726', linestyle='--', linewidth=0.8, alpha=0.7)
        ax5.axhline(30, color='#FF5252', linestyle='--', linewidth=0.8, alpha=0.7)
        ax5.set_title(f"VIX 恐慌指數 (5年走勢) — 最新：{latest_vix:.2f}", color='white', fontsize=13, pad=8, fontweight='bold')
        ax5.tick_params(colors='white')
        ax5.grid(color='#333333', linestyle=':', linewidth=0.6)
    else:
        ax5.axis('off')
        ax5.text(0.5, 0.5, "暫無法取得 VIX 數據", color='#AAAAAA', ha='center', va='center')

    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor=fig.get_facecolor())
    plt.close()

def send_telegram_photo(image_path):
    token = os.environ["TG_BOT_TOKEN"]
    chat_id = os.environ["TG_CHAT_ID"]
    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    caption = f"📊 台股盤前/盤後 市場總覽 ({NOW_STR})\n🔗 證交所擔保維持率：https://www.twse.com.tw/dashboard/zh/credit/general.html"
    with open(image_path, "rb") as img:
        resp = requests.post(url, data={"chat_id": chat_id, "caption": caption}, files={"photo": img}, timeout=20)
    resp.raise_for_status()
    print("Telegram 推播成功！")

if __name__ == "__main__":
    img_file = "market_report.png"
    build_dashboard(img_file)
    send_telegram_photo(img_file)