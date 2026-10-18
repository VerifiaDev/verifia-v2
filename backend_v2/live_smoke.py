"""Live smoke test: one claim per expected outcome against a running backend_v2.
Usage:  python live_smoke.py [base_url]     (default http://localhost:8000)
Start the server first:  cd backend_v2 && uvicorn app.main:app   (keys in backend_v2/.env)
Stdlib only. Each claim is a separate request so nothing is merged or cached together."""
import json, sys, time, urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000").rstrip("/")
CASES = [
    ("SUPPORTED",           "Ankara, Türkiye'nin başkentidir."),
    ("REFUTED",             "Türkiye'nin başkenti İstanbul'dur."),
    ("NOT ENOUGH EVIDENCE", "Kızılay Meydanı'nın altında 2019'da halka kapalı gizli bir müze açıldı."),
    ("OPINION (is_verifiable=false)", "Bence Ankara dünyanın en güzel şehridir."),
]

def norm(v): return (v or "").upper().replace("_", " ")

def post(text):
    req = urllib.request.Request(BASE + "/verify", data=json.dumps({"text": text}).encode(),
                                 headers={"Content-Type": "application/json"})
    t = time.time()
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return r.status, json.load(r), time.time() - t
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}"), time.time() - t

print("health:", json.load(urllib.request.urlopen(BASE + "/health", timeout=60)).get("status"))
ok_all = True
for expect, text in CASES:
    code, body, dt = post(text)
    res = (body.get("results") or [{}])[0]
    if expect.startswith("OPINION"):
        ok = res.get("is_verifiable") is False and res.get("verdict") is None
    else:
        ok = res.get("status") == "ok" and norm(res.get("verdict")) == expect
    ok_all &= ok
    print(f"\n[{'PASS' if ok else 'FAIL'}] expected {expect}  ({dt:.1f}s, HTTP {code})")
    print("  claim  :", res.get("claim"))
    print("  status :", res.get("status"), "| verdict:", res.get("verdict"), "| verifiable:", res.get("is_verifiable"),
          "| error:", res.get("error_code"))
    print("  explain:", (res.get("explanation") or "")[:300])
    print("  sources:", [s.get("url") for s in (res.get("sources") or res.get("evidence") or [])][:3])
print("\nALL PASS" if ok_all else "\nSOME FAILED - paste this output back to Claude")
