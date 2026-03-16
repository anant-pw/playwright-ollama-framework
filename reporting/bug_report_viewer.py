# reporting/bug_report_viewer.py
#
# CHANGE: Can show a specific run (default = latest run) or all runs.
# Run: python reporting/bug_report_viewer.py           → latest run
#      python reporting/bug_report_viewer.py --all     → all runs
#      python reporting/bug_report_viewer.py 20260316_171950 → specific run

import os, json, glob, datetime, platform, subprocess, sys
from config import CFG


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<title>Bug Report — {run_label}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f4f5f7;color:#172b4d}}
.header{{background:#0052cc;color:white;padding:20px 32px;display:flex;justify-content:space-between;align-items:flex-start}}
.header h1{{font-size:20px;font-weight:600}}
.header p{{font-size:12px;opacity:.8;margin-top:3px}}
.run-selector{{background:rgba(255,255,255,.15);border:1px solid rgba(255,255,255,.3);
  color:white;padding:6px 10px;border-radius:6px;font-size:12px;cursor:pointer}}
.run-selector option{{color:#172b4d;background:white}}
.summary{{display:flex;gap:12px;padding:16px 32px;background:white;border-bottom:1px solid #dfe1e6;flex-wrap:wrap}}
.stat{{text-align:center;padding:10px 20px;border-radius:8px;min-width:80px}}
.stat .num{{font-size:24px;font-weight:700}}
.stat .lbl{{font-size:11px;margin-top:2px;opacity:.7}}
.stat.total{{background:#e6f0ff;color:#0052cc}}
.stat.critical{{background:#ffebe6;color:#bf2600}}
.stat.high{{background:#ffebe6;color:#bf2600}}
.stat.medium{{background:#fffae6;color:#974f0c}}
.stat.low{{background:#e3fcef;color:#006644}}
.container{{max-width:1100px;margin:20px auto;padding:0 24px}}
.run-info{{background:white;border-radius:8px;padding:14px 20px;margin-bottom:16px;
  border:1px solid #dfe1e6;display:flex;gap:24px;align-items:center;font-size:13px}}
.run-info .label{{color:#6b778c;font-size:11px;font-weight:700;text-transform:uppercase;margin-bottom:2px}}
.bug-card{{background:white;border-radius:8px;margin-bottom:12px;border:1px solid #dfe1e6;overflow:hidden}}
.bug-header{{display:flex;align-items:center;gap:12px;padding:14px 18px;cursor:pointer}}
.bug-header:hover{{background:#f4f5f7}}
.bug-header.open{{border-bottom:1px solid #dfe1e6}}
.severity{{padding:3px 10px;border-radius:20px;font-size:11px;font-weight:700;text-transform:uppercase;white-space:nowrap}}
.sev-critical,.sev-high{{background:#ffebe6;color:#bf2600}}
.sev-medium{{background:#fffae6;color:#974f0c}}
.sev-low{{background:#e3fcef;color:#006644}}
.bug-title{{font-size:14px;font-weight:600;flex:1}}
.bug-meta{{font-size:11px;color:#6b778c;white-space:nowrap}}
.chevron{{font-size:11px;color:#6b778c;transition:transform .2s}}
.chevron.open{{transform:rotate(90deg)}}
.bug-body{{padding:18px;display:none}}
.bug-body.open{{display:block}}
.section{{margin-bottom:16px}}
.section h3{{font-size:11px;font-weight:700;color:#6b778c;text-transform:uppercase;letter-spacing:.06em;margin-bottom:6px}}
.description{{background:#f4f5f7;border-radius:6px;padding:10px 14px;font-size:13px;
  line-height:1.6;white-space:pre-wrap;border-left:3px solid #0052cc}}
.screenshot img{{max-width:100%;border-radius:6px;border:1px solid #dfe1e6;cursor:zoom-in;margin-top:6px}}
.no-bugs{{text-align:center;padding:60px;color:#6b778c}}
.filter-bar{{display:flex;gap:8px;margin-bottom:16px;flex-wrap:wrap}}
.filter-btn{{padding:5px 12px;border-radius:20px;border:1px solid #dfe1e6;background:white;font-size:12px;cursor:pointer}}
.filter-btn.active{{background:#0052cc;color:white;border-color:#0052cc}}
.lightbox{{display:none;position:fixed;inset:0;background:rgba(0,0,0,.85);z-index:1000;align-items:center;justify-content:center}}
.lightbox.open{{display:flex}}
.lightbox img{{max-width:90vw;max-height:90vh;border-radius:8px}}
.lbclose{{position:fixed;top:16px;right:24px;color:white;font-size:26px;cursor:pointer}}
</style></head><body>
<div class="header">
  <div>
    <h1>🐛 Bug Report</h1>
    <p>{run_label} · {total} bug(s) found</p>
  </div>
  <select class="run-selector" onchange="location.href=this.value">
    {run_options}
  </select>
</div>
<div class="summary">
  <div class="stat total"><div class="num">{total}</div><div class="lbl">Total</div></div>
  <div class="stat critical"><div class="num">{critical}</div><div class="lbl">Critical</div></div>
  <div class="stat high"><div class="num">{high}</div><div class="lbl">High</div></div>
  <div class="stat medium"><div class="num">{medium}</div><div class="lbl">Medium</div></div>
  <div class="stat low"><div class="num">{low}</div><div class="lbl">Low</div></div>
</div>
<div class="container">
  <div class="run-info">
    <div><div class="label">Run ID</div>{run_id}</div>
    <div><div class="label">Generated</div>{generated_at}</div>
    <div><div class="label">Location</div>{source_dir}</div>
  </div>
  <div class="filter-bar">
    <button class="filter-btn active" onclick="filter('all',this)">All</button>
    <button class="filter-btn" onclick="filter('Critical',this)">Critical</button>
    <button class="filter-btn" onclick="filter('High',this)">High</button>
    <button class="filter-btn" onclick="filter('Medium',this)">Medium</button>
    <button class="filter-btn" onclick="filter('Low',this)">Low</button>
  </div>
  {bug_cards}
</div>
<div class="lightbox" id="lb" onclick="closeLb()">
  <span class="lbclose">✕</span>
  <img id="lb-img" src="" alt="">
</div>
<script>
function toggle(id){{
  document.getElementById('body-'+id).classList.toggle('open');
  document.getElementById('hdr-'+id).classList.toggle('open');
  document.getElementById('chev-'+id).classList.toggle('open');
}}
function filter(sev,btn){{
  document.querySelectorAll('.filter-btn').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active');
  document.querySelectorAll('.bug-card').forEach(c=>{{
    c.style.display=(sev==='all'||c.dataset.sev===sev)?'':'none';
  }});
}}
function openLb(src){{document.getElementById('lb-img').src=src;document.getElementById('lb').classList.add('open');}}
function closeLb(){{document.getElementById('lb').classList.remove('open');}}
const first=document.querySelector('.bug-header');if(first)first.click();
</script></body></html>"""

CARD = """<div class="bug-card" data-sev="{severity}">
  <div class="bug-header" id="hdr-{idx}" onclick="toggle({idx})">
    <span class="severity sev-{sev_cls}">{severity}</span>
    <span class="bug-title">{title}</span>
    <span class="bug-meta">#{num} · {timestamp}</span>
    <span class="chevron" id="chev-{idx}">▶</span>
  </div>
  <div class="bug-body" id="body-{idx}">
    <div class="section"><h3>Description</h3>
      <div class="description">{description}</div></div>
    {steps_html}{screenshot_html}{info_html}
  </div>
</div>"""


def _runs_available() -> list:
    """Return list of (run_id, run_dir) sorted newest first."""
    base = CFG.bug_reports_dir
    runs = []
    if os.path.isdir(base):
        for name in sorted(os.listdir(base), reverse=True):
            d = os.path.join(base, name)
            if os.path.isdir(d) and name[0].isdigit():
                runs.append((name, d))
    return runs


def generate_html_report(run_id: str = None, output_path: str = None) -> str:
    runs = _runs_available()
    if not runs:
        print("[BUG REPORT] No run folders found.")
        return ""

    # Pick the run to display
    if run_id:
        matches = [(r, d) for r, d in runs if r == run_id]
        if not matches:
            print(f"[BUG REPORT] Run {run_id} not found.")
            return ""
        target_run_id, run_dir = matches[0]
    else:
        target_run_id, run_dir = runs[0]  # latest

    files = sorted(glob.glob(os.path.join(run_dir, "bug_*.json")))

    if output_path is None:
        output_path = os.path.join(run_dir, "bug_report_viewer.html")

    counts  = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
    cards   = []

    for idx, fpath in enumerate(files):
        try:
            bug = json.load(open(fpath, encoding="utf-8"))
        except Exception:
            continue

        sev = bug.get("severity", "Medium").strip().title()
        if sev not in counts:
            sev = "Medium"
        counts[sev] += 1

        # Steps
        steps = bug.get("steps_to_reproduce", [])
        steps_html = ""
        if steps:
            items = "".join(f"<li style='padding:6px 0;font-size:13px'>{s}</li>"
                            for s in steps)
            steps_html = f'<div class="section"><h3>Steps</h3><ol style="padding-left:20px">{items}</ol></div>'

        # Screenshot — path relative to the HTML file
        ss = bug.get("screenshot")
        ss_html = ""
        if ss:
            abs_ss = os.path.abspath(ss)
            if os.path.exists(abs_ss):
                rel = os.path.relpath(abs_ss, os.path.dirname(output_path)).replace("\\", "/")
                ss_html = (f'<div class="section"><h3>Screenshot</h3>'
                           f'<div class="screenshot"><img src="{rel}" '
                           f'onclick="openLb(this.src)" alt="screenshot"></div></div>')

        # Additional info
        info = bug.get("additional_info", {})
        info_html = ""
        if info:
            rows = "".join(
                f"<tr><td style='padding:5px 10px;color:#6b778c;font-size:12px;white-space:nowrap'>{k}</td>"
                f"<td style='padding:5px 10px;font-size:12px'>{v}</td></tr>"
                for k, v in info.items() if v
            )
            if rows:
                info_html = (f'<div class="section"><h3>Additional info</h3>'
                             f'<table style="border-collapse:collapse;background:#f4f5f7;'
                             f'border-radius:6px;width:100%">{rows}</table></div>')

        cards.append(CARD.format(
            idx=idx, num=idx+1, severity=sev, sev_cls=sev.lower(),
            title=bug.get("title", "Bug"),
            timestamp=bug.get("timestamp", ""),
            description=bug.get("description", "").replace("<", "&lt;"),
            steps_html=steps_html, screenshot_html=ss_html, info_html=info_html,
        ))

    # Run selector dropdown
    run_options = "\n".join(
        f'<option value="{r}/bug_report_viewer.html"'
        f'{" selected" if r == target_run_id else ""}>{r} ({len(glob.glob(os.path.join(d,"bug_*.json")))} bugs)</option>'
        for r, d in runs
    )

    html = HTML_TEMPLATE.format(
        run_id       = target_run_id,
        run_label    = f"Run {target_run_id}",
        generated_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        source_dir   = run_dir,
        total        = len(files),
        critical     = counts["Critical"],
        high         = counts["High"],
        medium       = counts["Medium"],
        low          = counts["Low"],
        bug_cards    = "\n".join(cards) if cards else '<div class="no-bugs"><p>No bugs in this run.</p></div>',
        run_options  = run_options,
    )

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"[BUG REPORT] → {output_path}  ({len(files)} bug(s), run {target_run_id})")
    return output_path


def open_report(path: str):
    try:
        s = platform.system()
        if s == "Windows": os.startfile(path)
        elif s == "Darwin": subprocess.Popen(["open", path])
        else:               subprocess.Popen(["xdg-open", path])
    except Exception:
        print(f"[BUG REPORT] Open manually: {path}")


if __name__ == "__main__":
    run_id = sys.argv[1] if len(sys.argv) > 1 else None
    path   = generate_html_report(run_id)
    if path:
        open_report(path)
