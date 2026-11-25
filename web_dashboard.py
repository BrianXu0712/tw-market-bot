import os
import json
from datetime import datetime, timedelta
from market_dashboard import build_dashboard, NOW_DT, TW_TZ

DOCS_DIR = "docs"
REPORTS_DIR = os.path.join(DOCS_DIR, "reports")
RETENTION_DAYS = 30


def cleanup_old_reports():
    """刪除超過 30 天的歷史圖表，並回傳剩餘檔案清單（由新到舊）"""
    cutoff = NOW_DT - timedelta(days=RETENTION_DAYS)
    valid_files = []

    for fname in os.listdir(REPORTS_DIR):
        if not fname.endswith(".png"):
            continue
        try:
            # 檔名格式：YYYY-MM-DD_HHMM.png
            dt_str = fname.replace(".png", "")
            file_dt = datetime.strptime(dt_str, "%Y-%m-%d_%H%M").replace(tzinfo=TW_TZ)
            if file_dt < cutoff:
                os.remove(os.path.join(REPORTS_DIR, fname))
            else:
                label = file_dt.strftime("%Y-%m-%d %H:%M")
                valid_files.append({"file": fname, "label": label})
        except ValueError:
            continue

    # 依檔名由新到舊排序
    valid_files.sort(key=lambda x: x["file"], reverse=True)
    return valid_files


def generate_html(reports):
    """產出單頁互動式儀表板 HTML（支援下拉選單與上下筆切換）"""
    reports_json = json.dumps(reports, ensure_ascii=False)
    updated_str = NOW_DT.strftime("%Y-%m-%d %H:%M CST")

    html = f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>台股盤前 / 盤後 市場總覽儀表板</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      padding: 16px;
      background-color: #121212;
      color: #EAEAEA;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans TC", sans-serif;
      display: flex;
      flex-direction: column;
      align-items: center;
    }}
    .container {{
      width: 100%;
      max-width: 1100px;
    }}
    header {{
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      margin-bottom: 16px;
      padding-bottom: 12px;
      border-bottom: 1px solid #2C2C2C;
    }}
    h1 {{
      margin: 0;
      font-size: 1.25rem;
      color: #FFFFFF;
    }}
    .meta {{
      font-size: 0.85rem;
      color: #9E9E9E;
    }}
    .controls {{
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 8px;
      margin-bottom: 16px;
      background: #1E1E1E;
      padding: 12px;
      border-radius: 10px;
    }}
    select {{
      flex: 1;
      min-width: 180px;
      padding: 8px 12px;
      font-size: 1rem;
      background: #2C2C2C;
      color: #FFFFFF;
      border: 1px solid #444;
      border-radius: 6px;
      cursor: pointer;
    }}
    button {{
      padding: 8px 14px;
      font-size: 0.95rem;
      background: #333333;
      color: #FFFFFF;
      border: 1px solid #555;
      border-radius: 6px;
      cursor: pointer;
    }}
    button:hover:not(:disabled) {{ background: #4A4A4A; }}
    button:disabled {{ opacity: 0.4; cursor: not-allowed; }}
    .chart-box {{
      background: #1E1E1E;
      padding: 8px;
      border-radius: 10px;
      text-align: center;
    }}
    .chart-box img {{
      width: 100%;
      height: auto;
      border-radius: 6px;
      display: block;
    }}
    .hint {{
      margin-top: 8px;
      font-size: 0.8rem;
      color: #888;
    }}
  </style>
</head>
<body>
  <div class="container">
    <header>
      <h1>📊 台股盤前 / 盤後 市場總覽</h1>
      <div class="meta">保留近 30 天紀錄 ｜ 最後更新：{updated_str}</div>
    </header>

    <div class="controls">
      <button id="prevBtn" onclick="step(-1)">◀ 較新</button>
      <select id="reportSelect" onchange="renderSelected()"></select>
      <button id="nextBtn" onclick="step(1)">較舊 ▶</button>
      <a id="rawLink" href="#" target="_blank" style="text-decoration:none;">
        <button type="button">🔍 另開原圖</button>
      </a>
    </div>

    <div class="chart-box">
      <img id="chartImg" src="" alt="市場總覽圖表">
      <div class="hint">手機可點「另開原圖」放大檢視細節</div>
    </div>
  </div>

  <script>
    const reports = {reports_json};
    const select = document.getElementById("reportSelect");
    const img = document.getElementById("chartImg");
    const rawLink = document.getElementById("rawLink");
    const prevBtn = document.getElementById("prevBtn");
    const nextBtn = document.getElementById("nextBtn");

    reports.forEach((item, idx) => {{
      const opt = document.createElement("option");
      opt.value = idx;
      opt.textContent = item.label + (idx === 0 ? " (最新)" : "");
      select.appendChild(opt);
    }});

    function renderSelected() {{
      if (reports.length === 0) return;
      const idx = parseInt(select.value, 10);
      const path = "reports/" + reports[idx].file;
      img.src = path;
      rawLink.href = path;
      prevBtn.disabled = (idx === 0);
      nextBtn.disabled = (idx === reports.length - 1);
    }}

    function step(delta) {{
      const nextIdx = parseInt(select.value, 10) + delta;
      if (nextIdx >= 0 && nextIdx < reports.length) {{
        select.value = nextIdx;
        renderSelected();
      }}
    }}

    renderSelected();
  </script>
</body>
</html>
"""
    with open(os.path.join(DOCS_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)


if __name__ == "__main__":
    os.makedirs(REPORTS_DIR, exist_ok=True)
    filename = f"{NOW_DT.strftime('%Y-%m-%d_%H%M')}.png"
    filepath = os.path.join(REPORTS_DIR, filename)

    # 直接呼叫原本 market_dashboard.py 的繪圖函式
    build_dashboard(filepath)

    # 清理超過 30 天的舊圖並重建網頁
    reports = cleanup_old_reports()
    generate_html(reports)
    print(f"網頁更新完成，目前保留 {len(reports)} 筆圖表。")
