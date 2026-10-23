"""Self-contained report. No scripts, network resources, or embedded raw JSON."""
from html import escape


def render(result):
    rows = []
    for c in result["changes"]:
        lost = ''.join('<li><b>' + escape(s['document']) +
                       f' · [{s["start"]}, {s["end"]})</b><pre>' + escape(s['text']) + '</pre></li>'
                       for s in c['after']['missing'])
        state = 'regression' if c['regressed'] else 'pass'
        rows.append(f'''<article class="{state}"><div class="label">{escape(c['id'])} · {state}</div>
<h2>{escape(c['question'])}</h2><p class="score">{c['before']['coverage']:.1%} → {c['after']['coverage']:.1%}
<span>({c['delta'] * 100:+.1f} pp)</span></p>
<p>Context: {c['before']['context_chars']:,} → {c['after']['context_chars']:,} characters ·
Duplicate context: {c['after']['duplicate_context_chars']:,} characters</p>
<details {'open' if lost else ''}><summary>Missing evidence in candidate</summary>
<ul>{lost or '<li>All labeled evidence is present.</li>'}</ul></details></article>''')
    status = 'REGRESSION DETECTED' if not result['passed'] else 'GATE PASSED'
    return '''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'">
<title>Retrieval Delta · Retrieval regression report</title><style>
*{box-sizing:border-box}body{background:#f6f5ef;color:#172b28;font:16px/1.6 system-ui,sans-serif;margin:0}
main{max-width:960px;margin:auto;padding:50px 24px}header{border-bottom:2px solid #173d34;padding-bottom:26px}
.brand{font-weight:800;letter-spacing:.12em}h1{font-size:clamp(32px,5vw,55px);line-height:1.1;max-width:750px}
.sub{color:#50625d;max-width:690px}.stats{display:flex;gap:24px;flex-wrap:wrap;margin:30px 0}
.stat{flex:1;min-width:170px;border-top:1px solid #b9c8bf;padding-top:12px}.stat strong{display:block;font-size:32px}
article{background:white;padding:24px;margin:18px 0;border:1px solid #d6dfd9;border-left:5px solid #35806b}
article.regression{border-left-color:#bf4c32}.label{font-size:12px;text-transform:uppercase;letter-spacing:.1em}
h2{font-size:21px;margin:8px 0}.score{font-size:28px;font-weight:700;margin:10px 0}.score span{font-size:16px}
pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#fff3d9;padding:14px;font:15px/1.6 ui-monospace,monospace}
summary{cursor:pointer}li{margin:12px 0}footer{font-size:13px;color:#50625d;margin-top:30px}
</style><main><header><div class="brand">EVIDIFF / RETRIEVAL CHECK</div>
<h1>Find the evidence your retriever lost.</h1>
<p class="sub">A source-anchored diff. No model judge, no API keys. Coverage measures labeled evidence present in retrieved context; it does not certify answer correctness.</p>
</header>''' + f'''<div class="stats"><div class="stat">{status}<strong>{result['regressions']} regressions</strong></div>
<div class="stat">Mean evidence coverage @ {result['k']}<strong>{result['baseline']['coverage']:.1%} → {result['candidate']['coverage']:.1%}</strong></div>
<div class="stat">Candidate complete cases<strong>{result['candidate']['complete_cases']} / {len(result['changes'])}</strong></div></div>
''' + ''.join(rows) + f'''<footer>Allowed per-case coverage drop: {result['max_drop'] * 100:g} percentage points.
Offsets are Unicode characters [start, end). Report includes source excerpts: review before sharing.
No telemetry · Generated locally by Retrieval Delta 0.1.0</footer></main></html>'''
