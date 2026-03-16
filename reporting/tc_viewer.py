# reporting/tc_viewer.py
#
# CHANGE: Shows TCs for a specific run (default = latest) with run selector.

import os, glob, datetime, platform, subprocess, sys, base64
from config import CFG


def _runs_available() -> list:
    """Return list of (run_id, tc_file) sorted newest first."""
    base = "generated_test_cases"
    runs = []
    if os.path.isdir(base):
        for name in sorted(os.listdir(base), reverse=True):
            tc = os.path.join(base, name, "test_cases.xlsx")
            if os.path.exists(tc):
                runs.append((name, tc))
    return runs


def generate_html_viewer(run_id: str = None, output_path: str = None) -> str:
    try:
        import pandas as pd
    except ImportError:
        print("[TC VIEWER] pandas not installed.")
        return ""

    runs = _runs_available()
    if not runs:
        print("[TC VIEWER] No TC run folders found.")
        return ""

    if run_id:
        matches = [(r, f) for r, f in runs if r == run_id]
        if not matches:
            print(f"[TC VIEWER] Run {run_id} not found.")
            return ""
        target_run_id, tc_file = matches[0]
    else:
        target_run_id, tc_file = runs[0]  # latest

    df = pd.read_excel(tc_file)
    if df.empty:
        print("[TC VIEWER] No TCs in this run.")
        return ""

    run_dir = os.path.dirname(tc_file)
    if output_path is None:
        output_path = os.path.join(run_dir, "tc_viewer.html")

    rows_html = ""
    for _, row in df.iterrows():
        rows_html += f"""<tr>
          <td class="tc-id">{row.get('TestID','')}</td>
          <td class="tc-title">{row.get('Title','')}</td>
          <td>{row.get('Steps','')}</td>
          <td>{row.get('ExpectedResult','')}</td>
          <td class="tc-url" title="{row.get('URL','')}">{str(row.get('URL',''))[:40]}…</td>
          <td class="tc-date">{row.get('CreatedAt','')}</td>
        </tr>"""

    with open(tc_file, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()

    run_options = "\n".join(
        f'<option value="{r}/tc_viewer.html"{" selected" if r == target_run_id else ""}>'
        f'{r} ({len(pd.read_excel(fi))} TCs)</option>'
        for r, fi in runs
    )

    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<title>Test Cases — Run {target_run_id}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f4f5f7;color:#172b4d}}
.header{{background:#0052cc;color:white;padding:20px 32px;display:flex;justify-content:space-between;align-items:center}}
.header h1{{font-size:20px;font-weight:600}}
.header p{{font-size:12px;opacity:.8;margin-top:3px}}
.run-selector{{background:rgba(255,255,255,.15);border:1px solid rgba(255,255,255,.3);
  color:white;padding:6px 10px;border-radius:6px;font-size:12px}}
.run-selector option{{color:#172b4d;background:white}}
.dl-btn{{padding:8px 16px;background:white;color:#0052cc;border-radius:6px;
  text-decoration:none;font-weight:700;font-size:12px;white-space:nowrap}}
.toolbar{{background:white;padding:10px 32px;border-bottom:1px solid #dfe1e6;
  display:flex;gap:12px;align-items:center}}
.search{{padding:7px 12px;border:1px solid #dfe1e6;border-radius:6px;font-size:13px;width:260px}}
.count{{color:#6b778c;font-size:12px}}
.container{{padding:20px 32px}}
table{{width:100%;border-collapse:collapse;background:white;border-radius:8px;overflow:hidden;
  box-shadow:0 1px 3px rgba(0,0,0,.07)}}
th{{background:#f4f5f7;padding:9px 12px;text-align:left;font-size:11px;font-weight:700;
  color:#6b778c;text-transform:uppercase;letter-spacing:.05em;border-bottom:2px solid #dfe1e6}}
td{{padding:10px 12px;border-bottom:1px solid #f4f5f7;font-size:13px;vertical-align:top}}
tr:last-child td{{border-bottom:none}}
tr:hover td{{background:#f8f9ff}}
.tc-id{{font-family:monospace;font-size:11px;color:#6b778c;white-space:nowrap}}
.tc-title{{font-weight:600;color:#0052cc}}
.tc-url{{font-size:11px;color:#6b778c}}
.tc-date{{font-size:11px;color:#6b778c;white-space:nowrap}}
.hidden{{display:none}}
</style></head><body>
<div class="header">
  <div>
    <h1>🧪 Test Cases</h1>
    <p>Run {target_run_id} · {len(df)} test cases</p>
  </div>
  <div style="display:flex;gap:12px;align-items:center">
    <select class="run-selector" onchange="location.href='../'+this.value">
      {run_options}
    </select>
    <a class="dl-btn"
       href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}"
       download="test_cases_{target_run_id}.xlsx">⬇ Excel</a>
  </div>
</div>
<div class="toolbar">
  <input class="search" type="text" placeholder="Search…" oninput="search(this.value)">
  <span class="count" id="count">{len(df)} test cases</span>
  <span style="color:#6b778c;font-size:12px;margin-left:auto">Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}</span>
</div>
<div class="container">
  <table><thead>
    <tr><th>Test ID</th><th>Title</th><th>Steps</th><th>Expected</th><th>URL</th><th>Created</th></tr>
  </thead><tbody id="tbody">{rows_html}</tbody></table>
</div>
<script>
function search(q){{
  const rows=document.querySelectorAll('#tbody tr');
  let v=0; q=q.toLowerCase();
  rows.forEach(r=>{{const m=r.textContent.toLowerCase().includes(q);r.classList.toggle('hidden',!m);if(m)v++;}});
  document.getElementById('count').textContent=v+' test cases';
}}
</script></body></html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"[TC VIEWER] → {output_path}  ({len(df)} TCs, run {target_run_id})")
    return output_path


def open_viewer(path: str):
    try:
        s = platform.system()
        if s == "Windows": os.startfile(path)
        elif s == "Darwin": subprocess.Popen(["open", path])
        else:               subprocess.Popen(["xdg-open", path])
    except Exception:
        print(f"[TC VIEWER] Open manually: {path}")


if __name__ == "__main__":
    run_id = sys.argv[1] if len(sys.argv) > 1 else None
    path   = generate_html_viewer(run_id)
    if path:
        open_viewer(path)
