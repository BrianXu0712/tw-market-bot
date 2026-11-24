import os
import requests
import numpy as np
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.patches import Wedge, Polygon, Circle
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
    # 加上當前時間戳記 (t=...) 強制繞過 CNN 的 CDN 快取
    ts = int(datetime.now().timestamp())
    url = f"https://production.dataviz.cnn.io/index/fearandgreed/graphdata?t={ts}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://edition.cnn.com/",
        "Accept": "application/json, text/plain, */*",
    }
    try:
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        data = r.json()
        fg = data.get("fear_and_greed", {})
        print("CNN API 原始更新時間:", fg.get("timestamp"))  # 方便在 GitHub Actions log 核對
        return {
            "score": round(fg.get("score", 0)),
            "rating": fg.get("rating", "N/A").title(),
            "prev_close": round(fg.get("previous_close", 0)),
            "prev_1w": round(fg.get("previous_1_week", 0)),
            "prev_1m": round(fg.get("previous_1_month", 0)),
            "prev_1y": round(fg.get("previous_1_year", 0)),
        }
    except Exception as e:
        print("CNN 抓取失敗:", e)
        return None


def get_fg_style(score):
    """依分數回傳 CNN 風格的狀態名稱、底色與邊框色"""
    if score < 25:
        return "Extreme Fear", "#F4C2C2", "#A62C2B"
    elif score < 45:
        return "Fear", "#F8DFC2", "#C87A28"
    elif score < 55:
        return "Neutral", "#E5E5E5", "#666666"
    elif score < 75:
        return "Greed", "#C8E6C9", "#2E7D32"
    else:
        return "Extreme Greed", "#A5D6A7", "#1B5E20"


def draw_cnn_gauge(ax, fg):
    """繪製仿 CNN Business 風格的恐懼與貪婪指數儀表板"""
    ax.set_facecolor('white')
    ax.set_aspect('equal')
    ax.set_xlim(-1.25, 1.25)
    ax.set_ylim(-1.12, 1.18)
    ax.axis('off')

    # 白底卡片外框
    rect = plt.Rectangle((-1.25, -1.12), 2.5, 2.3, facecolor='white', edgecolor='#DDDDDD', linewidth=1.2, zorder=0)
    ax.add_patch(rect)

    ax.text(-1.15, 1.03, "Fear & Greed Index", fontsize=13, fontweight='bold', color='#111111', ha='left')

    if not fg:
        ax.text(0, 0, "暫無法取得 CNN 數據", color='#666666', ha='center', va='center', fontsize=11)
        return

    score = max(0, min(100, fg['score']))
    cy = 0.02  # 半圓圓心 Y 座標

    # 五個區間：(起始分數, 結束分數, 標籤)
    sectors = [
        (0, 25, "EXTREME\nFEAR"),
        (25, 45, "FEAR"),
        (45, 55, "NEUTRAL"),
        (55, 75, "GREED"),
        (75, 100, "EXTREME\nGREED"),
    ]

    for s_min, s_max, label in sectors:
        theta2 = 180 - s_min * 1.8
        theta1 = 180 - s_max * 1.8
        is_active = (s_min <= score < s_max) or (s_max == 100 and score == 100)

        if is_active:
            _, fill_c, edge_c = get_fg_style(score)
            lw = 1.6
            txt_color = '#111111'
            z = 3
        else:
            fill_c, edge_c = '#F2F2F2', 'white'
            lw = 2.0
            txt_color = '#555555'
            z = 2

        wedge = Wedge((0, cy), 0.92, theta1, theta2, width=0.34,
                      facecolor=fill_c, edgecolor=edge_c, linewidth=lw, zorder=z)
        ax.add_patch(wedge)

        # 區間文字
        mid_ang = (theta1 + theta2) / 2
        rad = np.deg2rad(mid_ang)
        ax.text(0.75 * np.cos(rad), cy + 0.75 * np.sin(rad), label,
                ha='center', va='center', fontsize=7.5, fontweight='bold',
                color=txt_color, rotation=mid_ang - 90, zorder=4)

    # 刻度數字 (0, 25, 50, 75, 100) 與小圓點
    for val in range(0, 101, 5):
        ang = np.deg2rad(180 - val * 1.8)
        if val in (0, 25, 50, 75, 100):
            r_num = 0.50 if val in (25, 50, 75) else 0.51
            y_off = 0.03 if val in (0, 100) else 0
            ax.text(r_num * np.cos(ang), cy + r_num * np.sin(ang) + y_off, str(val),
                    ha='center', va='center', fontsize=8.5, color='#666666', zorder=4)
        else:
            ax.plot(0.51 * np.cos(ang), cy + 0.51 * np.sin(ang), 'o',
                    markersize=1.5, color='#999999', zorder=4)

    # 黑色指針
    needle_ang = np.deg2rad(180 - score * 1.8)
    perp = needle_ang + np.pi / 2
    tip = (0.78 * np.cos(needle_ang), cy + 0.78 * np.sin(needle_ang))
    base_l = (0.20 * np.cos(needle_ang) + 0.025 * np.cos(perp), cy + 0.20 * np.sin(needle_ang) + 0.025 * np.sin(perp))
    base_r = (0.20 * np.cos(needle_ang) - 0.025 * np.cos(perp), cy + 0.20 * np.sin(needle_ang) - 0.025 * np.sin(perp))
    ax.add_patch(Polygon([tip, base_l, base_r], closed=True, facecolor='#1A1A1A', zorder=5))

    # 中央最新分數
    ax.text(0, cy + 0.10, str(score), fontsize=24, fontweight='bold', color='#111111', ha='center', va='center', zorder=6)

    # 下方 4 列歷史數據
    history_rows = [
        ("Previous close", fg['prev_close']),
        ("1 week ago", fg['prev_1w']),
        ("1 month ago", fg['prev_1m']),
        ("1 year ago", fg['prev_1y']),
    ]
    y_start = -0.18
    for idx, (title, val) in enumerate(history_rows):
        y = y_start - idx * 0.24
        label_txt, b_fill, b_edge = get_fg_style(val)
        ax.text(-1.12, y + 0.05, title, fontsize=8, color='#666666', ha='left', va='center')
        ax.text(-1.12, y - 0.06, label_txt, fontsize=9.5, fontweight='bold', color='#111111', ha='left', va='center')
        # 虛線
        ax.plot([-0.25, 0.85], [y - 0.05, y - 0.05], linestyle=':', color='#DDDDDD', linewidth=0.9)
        # 右側圓形徽章
        badge = Circle((1.02, y - 0.01), 0.085, facecolor=b_fill, edgecolor=b_edge, linewidth=1.2, zorder=4)
        ax.add_patch(badge)
        ax.text(1.02, y - 0.01, str(val), fontsize=9, fontweight='bold', color='#111111', ha='center', va='center', zorder=5)


def get_taifex_txf():
    """抓取期交所台指期最新報價"""
    url = "https://mis.taifex.com.tw/futures/api/getQuoteList"
    payload = {
        "MarketType": "1",
        "SymbolType": "F",
        "KindID": "1",
        "CID": "TXF",
        "ExpireMonth": "",
        "RowSize": "全部",
        "PageNo": "",
        "SortColumn": "",
        "AscDesc": "A",
    }
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
    fig = plt.figure(figsize=(14, 12), facecolor='#121212')
    gs = gridspec.GridSpec(3, 2, figure=fig, height_ratios=[0.9, 1.65, 1.0], hspace=0.35, wspace=0.22)

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
            color = '#FF5252' if chg >= 0 else '#00E676'
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

    # --- 3. CNN 恐懼與貪婪指數 (仿官方半圓儀表板) ---
    ax3 = fig.add_subplot(gs[1, 0])
    fg = get_cnn_fear_greed()
    draw_cnn_gauge(ax3, fg)

    # --- 4. 美聯儲隱含利率 (Fed Funds Futures) ---
    ax4 = fig.add_subplot(gs[1, 1])
    ax4.set_facecolor('#1E1E1E')
    ax4.set_title("美聯儲利率期貨隱含水準 (ZQ=F)", color='white', fontsize=13, pad=10, fontweight='bold')
    ax4.axis('off')
    zq_price, implied = get_fed_implied_rate()
    if zq_price:
        ax4.text(0.05, 0.65, f"期貨價格：{zq_price}", color='white', fontsize=13, transform=ax4.transAxes)
        ax4.text(0.05, 0.42, f"市場隱含利率：約 {implied:.2f}%", color='#80CBC4', fontsize=16, fontweight='bold', transform=ax4.transAxes)
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
