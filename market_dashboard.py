import os
import math
import requests
import numpy as np
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.patches import Wedge, Polygon, Circle, Rectangle
from datetime import datetime, timezone, timedelta

# 設定中文字型（對應 GitHub Actions 安裝的 Noto Sans CJK）
plt.rcParams['font.sans-serif'] = ['Noto Sans CJK TC', 'Noto Sans CJK JP', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

TW_TZ = timezone(timedelta(hours=8))
NOW_DT = datetime.now(TW_TZ)
NOW_STR = NOW_DT.strftime('%Y-%m-%d %H:%M')

# 聯準會 FOMC 利率決議時間（台灣時間 UTC+8）
FOMC_DATES = [
    datetime(2026, 12, 10, 3, 0, tzinfo=TW_TZ),
    datetime(2027, 1, 28, 3, 0, tzinfo=TW_TZ),
    datetime(2027, 3, 18, 2, 0, tzinfo=TW_TZ),
    datetime(2027, 4, 29, 2, 0, tzinfo=TW_TZ),
    datetime(2027, 6, 17, 2, 0, tzinfo=TW_TZ),
    datetime(2027, 7, 29, 2, 0, tzinfo=TW_TZ),
    datetime(2027, 9, 23, 2, 0, tzinfo=TW_TZ),
    datetime(2027, 11, 4, 2, 0, tzinfo=TW_TZ),
    datetime(2027, 12, 16, 3, 0, tzinfo=TW_TZ),
]


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
        fg = r.json().get("fear_and_greed", {})
        return {
            "score": round(fg.get("score", 0)),
            "rating": fg.get("rating", "N/A").title(),
            "prev_close": round(fg.get("previous_close", 0)),
            "prev_1w": round(fg.get("previous_1_week", 0)),
            "prev_1m": round(fg.get("previous_1_month", 0)),
            "prev_1y": round(fg.get("previous_1_year", 0)),
        }
    except Exception:
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

    rect = Rectangle((-1.25, -1.12), 2.5, 2.3, facecolor='white', edgecolor='#DDDDDD', linewidth=1.2, zorder=0)
    ax.add_patch(rect)
    ax.text(-1.15, 1.03, "Fear & Greed Index", fontsize=13, fontweight='bold', color='#111111', ha='left')

    if not fg:
        ax.text(0, 0, "暫無法取得 CNN 數據", color='#666666', ha='center', va='center', fontsize=11)
        return

    score = max(0, min(100, fg['score']))
    cy = 0.02

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

        mid_ang = (theta1 + theta2) / 2
        rad = np.deg2rad(mid_ang)
        ax.text(0.75 * np.cos(rad), cy + 0.75 * np.sin(rad), label,
                ha='center', va='center', fontsize=7.5, fontweight='bold',
                color=txt_color, rotation=mid_ang - 90, zorder=4)

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

    needle_ang = np.deg2rad(180 - score * 1.8)
    perp = needle_ang + np.pi / 2
    tip = (0.78 * np.cos(needle_ang), cy + 0.78 * np.sin(needle_ang))
    base_l = (0.20 * np.cos(needle_ang) + 0.025 * np.cos(perp), cy + 0.20 * np.sin(needle_ang) + 0.025 * np.sin(perp))
    base_r = (0.20 * np.cos(needle_ang) - 0.025 * np.cos(perp), cy + 0.20 * np.sin(needle_ang) - 0.025 * np.sin(perp))
    ax.add_patch(Polygon([tip, base_l, base_r], closed=True, facecolor='#1A1A1A', zorder=5))

    ax.text(0, cy + 0.10, str(score), fontsize=24, fontweight='bold', color='#111111', ha='center', va='center', zorder=6)

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
        ax.plot([-0.25, 0.85], [y - 0.05, y - 0.05], linestyle=':', color='#DDDDDD', linewidth=0.9)
        badge = Circle((1.02, y - 0.01), 0.085, facecolor=b_fill, edgecolor=b_edge, linewidth=1.2, zorder=4)
        ax.add_patch(badge)
        ax.text(1.02, y - 0.01, str(val), fontsize=9, fontweight='bold', color='#111111', ha='center', va='center', zorder=5)


def get_next_fomc():
    for dt in FOMC_DATES:
        if dt > NOW_DT:
            return dt
    return FOMC_DATES[-1]


def rate_to_probs(implied_rate):
    """將隱含利率轉換為相鄰兩個 0.25% 區間的機率分佈"""
    # 每個區間中點為 0.125 + k * 0.25 (例如 4.00-4.25 中點為 4.125)
    k = math.floor((implied_rate - 0.125) / 0.25)
    low_band_start = round(k * 0.25, 2)
    high_band_start = round((k + 1) * 0.25, 2)
    low_mid = low_band_start + 0.125

    prob_high = max(0.0, min(1.0, (implied_rate - low_mid) / 0.25)) * 100.0
    prob_low = 100.0 - prob_high
    return {
        low_band_start: round(prob_low, 1),
        high_band_start: round(prob_high, 1),
    }


def get_fed_monitor_data():
    """抓取 ZQ=F 近一個月收盤價，計算目前、上一日、上星期的機率分佈"""
    try:
        df = yf.Ticker("ZQ=F").history(period="1mo")
        if df.empty:
            return None
        closes = df['Close'].dropna()
        p_now = float(closes.iloc[-1])
        p_prev = float(closes.iloc[-2]) if len(closes) >= 2 else p_now
        p_week = float(closes.iloc[-6]) if len(closes) >= 6 else float(closes.iloc[0])

        probs_now = rate_to_probs(100.0 - p_now)
        probs_prev = rate_to_probs(100.0 - p_prev)
        probs_week = rate_to_probs(100.0 - p_week)

        # 找出目前機率最高的主區間，並取其上下共 3 個區間顯示於表格
        main_band = max(probs_now, key=probs_now.get)
        bands = [round(main_band - 0.25, 2), main_band, round(main_band + 0.25, 2)]

        return {
            "price": round(p_now, 3),
            "bands": bands,
            "now": probs_now,
            "prev": probs_prev,
            "week": probs_week,
        }
    except Exception:
        return None


def draw_fed_monitor(ax, fed_data):
    """繪製仿 Investing.com 風格的美聯儲利率監測工具卡片"""
    ax.set_facecolor('white')
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis('off')

    # 白底卡片外框
    ax.add_patch(Rectangle((0, 0), 10, 10, facecolor='white', edgecolor='#DDDDDD', linewidth=1.2, zorder=0))

    # 頂部深色標題列
    ax.add_patch(Rectangle((0, 9.05), 10, 0.95, facecolor='#1A1A1A', zorder=1))
    ax.text(5.0, 9.52, "美聯儲利率監測工具", color='white', fontsize=12.5, fontweight='bold', ha='center', va='center', zorder=2)

    # 下一次 FOMC 倒數計算
    next_fomc = get_next_fomc()
    delta = next_fomc - NOW_DT
    total_mins = max(0, int(delta.total_seconds() // 60))
    weeks = total_mins // (7 * 24 * 60)
    rem = total_mins % (7 * 24 * 60)
    days = rem // (24 * 60)
    rem = rem % (24 * 60)
    hours = rem // 60
    mins = rem % 60

    fomc_date_str = next_fomc.strftime('%Y年%m月%d日')
    fomc_full_str = next_fomc.strftime('%Y年%m月%d日 %H:%M')

    # 倒數標題與四欄數字
    ax.text(5.0, 8.55, f"聯儲局利率決議 {fomc_full_str}", color='#555555', fontsize=9.5, ha='center', va='center')
    cd_items = [(str(weeks), "週"), (str(days), "日"), (str(hours), "小時"), (str(mins), "分鐘")]
    x_positions = [1.8, 3.9, 6.1, 8.2]
    for i, (num, unit) in enumerate(cd_items):
        ax.text(x_positions[i], 7.82, num, color='#111111', fontsize=15, fontweight='bold', ha='center', va='center')
        ax.text(x_positions[i], 7.32, unit, color='#777777', fontsize=8.5, ha='center', va='center')
        if i < 3:
            ax.plot([x_positions[i] + 1.05, x_positions[i] + 1.05], [7.25, 8.05], color='#E5E5E5', linewidth=1.0)

    # 灰色分隔帶
    ax.add_patch(Rectangle((0.02, 6.82), 9.96, 0.18, facecolor='#F0F0F0', edgecolor='none'))

    if not fed_data:
        ax.text(5.0, 3.5, "暫無法取得利率期貨數據", color='#666666', fontsize=11, ha='center', va='center')
        return

    # 會議時間與期貨價格
    ax.text(0.4, 6.42, fomc_date_str, color='#111111', fontsize=11, fontweight='bold', ha='left', va='center')
    ax.plot([0.3, 9.7], [6.10, 6.10], color='#EEEEEE', linewidth=1.0)
    ax.text(0.4, 5.70, "會議時間：", color='#555555', fontsize=9.5, ha='left', va='center')
    ax.text(2.3, 5.70, fomc_full_str, color='#111111', fontsize=9.5, fontweight='bold', ha='left', va='center')
    ax.text(0.4, 5.25, "期貨價格：", color='#555555', fontsize=9.5, ha='left', va='center')
    ax.text(2.3, 5.25, f"{fed_data['price']:.3f}", color='#111111', fontsize=9.5, fontweight='bold', ha='left', va='center')
    ax.plot([0.3, 9.7], [4.90, 4.90], color='#EEEEEE', linewidth=1.0)

    # 橫向機率長條圖（僅顯示目前機率 > 0% 的區間）
    active_bars = [(b, fed_data['now'].get(b, 0.0)) for b in fed_data['bands'] if fed_data['now'].get(b, 0.0) > 0]
    y_bar = 4.42
    for b, pct in active_bars[:2]:
        label = f"{b:.2f} - {b + 0.25:.2f}"
        ax.text(0.4, y_bar, label, color='#333333', fontsize=9.2, ha='left', va='center')
        bar_w = max(0.08, (pct / 100.0) * 5.2)
        ax.add_patch(Rectangle((2.5, y_bar - 0.16), bar_w, 0.32, facecolor='#E0E0E0', edgecolor='none'))
        ax.text(9.6, y_bar, f"{pct:.1f}%", color='#222222', fontsize=9.5, ha='right', va='center')
        y_bar -= 0.58

    ax.plot([0.3, 9.7], [3.40, 3.40], color='#DDDDDD', linewidth=1.0)

    # 下方對照表格
    ax.text(0.4, 3.00, "目標利率", color='#111111', fontsize=9.5, fontweight='bold', ha='left', va='center')
    ax.text(4.6, 3.00, "目前", color='#111111', fontsize=9.5, fontweight='bold', ha='right', va='center')
    ax.text(7.1, 3.00, "上一日", color='#111111', fontsize=9.5, fontweight='bold', ha='right', va='center')
    ax.text(9.6, 3.00, "上星期", color='#111111', fontsize=9.5, fontweight='bold', ha='right', va='center')
    ax.plot([0.3, 9.7], [2.72, 2.72], color='#EEEEEE', linewidth=1.0)
    ax.plot([2.85, 2.85], [0.75, 3.35], color='#EEEEEE', linewidth=1.0)

    def fmt_p(val):
        return f"{val:.1f}%" if val and val > 0 else "—"

    y_row = 2.32
    for b in fed_data['bands']:
        label = f"{b:.2f} - {b + 0.25:.2f}"
        ax.text(0.4, y_row, label, color='#111111', fontsize=9.2, fontweight='bold', ha='left', va='center')
        ax.text(4.6, y_row, fmt_p(fed_data['now'].get(b, 0)), color='#333333', fontsize=9.2, ha='right', va='center')
        ax.text(7.1, y_row, fmt_p(fed_data['prev'].get(b, 0)), color='#333333', fontsize=9.2, ha='right', va='center')
        ax.text(9.6, y_row, fmt_p(fed_data['week'].get(b, 0)), color='#333333', fontsize=9.2, ha='right', va='center')
        y_row -= 0.56

    # 底部更新時間
    ax.text(9.6, 0.32, f"已更新：{NOW_DT.strftime('%Y年%m月%d日 %H:%M')} CST", color='#888888', fontsize=8, ha='right', va='center')


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


def build_dashboard(output_path="market_report.png"):
    fig = plt.figure(figsize=(14, 13), facecolor='#121212')
    gs = gridspec.GridSpec(3, 2, figure=fig, height_ratios=[0.85, 1.85, 0.95], hspace=0.32, wspace=0.18)

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

    # --- 3. CNN 恐懼與貪婪指數 ---
    ax3 = fig.add_subplot(gs[1, 0])
    fg = get_cnn_fear_greed()
    draw_cnn_gauge(ax3, fg)

    # --- 4. 美聯儲利率監測工具 ---
    ax4 = fig.add_subplot(gs[1, 1])
    fed_data = get_fed_monitor_data()
    draw_fed_monitor(ax4, fed_data)

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
