"""One-off preparation of 'sleeping beauty' trade marks from the UK IPO open data snapshot.
Source: IPO 'Trade mark data release', Open Data: Domestic UK Applications (OGL v3), snapshot dated Feb 2018.
https://www.gov.uk/government/publications/ipo-trade-mark-data-release
The IPO has not published a newer bulk file (it paused bulk data during its systems transformation),
so status here is 'as of Feb 2018' and every lead links to the live IPO register to check today's status.
Usage: python3 prepare_trademarks.py /path/to/OpenDataDomestic.txt"""
import csv, io, json, sys, re, collections, os
LUX = {14: "watches & jewellery", 3: "perfume & cosmetics", 33: "wines & spirits", 12: "motoring & coachbuilding",
       18: "leather goods", 25: "tailoring & fashion", 43: "hotels & dining", 24: "fine textiles", 21: "porcelain & glass", 8: "cutlery & blades"}
W = {14: 1.0, 3: .9, 33: .95, 12: .9, 18: .85, 25: .75, 43: .8, 24: .6, 21: .7, 8: .6}
GENERIC = re.compile(r"^(THE |NEW |SUPER |DE LUXE|SPECIAL|EXTRA|GOLD|SILVER|ROYAL|STAR|CROWN|BEST|FINE|PURE|QUALITY|BRAND)$|\d{3,}|^[A-Z]{1,3}$|^[^A-Z]*$", re.I)
STOP = set("THE OF AND CO CIE SONS SON BROS BROTHERS LIMITED LTD BRAND WHISKY WHISKEY SCOTCH GIN RUM PORT SHERRY WINE WINES BRANDY COGNAC MALT OLD FINE FAMED PURE GENUINE BEST REAL ROYAL SPECIAL FINEST DE LA LE ET FILS FRERES MAISON HOUSE LONDON PARIS PRIZE MEDAL".split())
src = sys.argv[1]
f = io.open(src, encoding="utf-16")
r = csv.reader(f, delimiter="|")
hdr = [h.strip() for h in next(r)]
ix = {h: i for i, h in enumerate(hdr)}
LIVE = {"Registered", "Application Published", "Examination", "Opposed", "Pre-Publication", "Appealable", "Registration Pending", "Application Received"}
live_text = set(); live_grams = set(); owner_live = collections.Counter(); cands = []
for row in r:
    if len(row) < len(hdr): continue
    g = lambda k: row[ix[k]].strip()
    st = g("Status"); text = g("Mark Text"); owner = g("Name")
    norm = re.sub(r"[^A-Z0-9 ]", "", text.upper()).strip()
    if st in LIVE:
        live_text.add(norm); owner_live[owner.lower()] += 1
        t = norm.split()
        for n in (1, 2, 3):
            for i in range(len(t) - n + 1):
                live_grams.add(" ".join(t[i:i + n]))
        continue
    if st not in ("Dead", "Expired", "Removed", "Surrendered"): continue
    classes = [c for c in range(1, 46) if g(f"Class{c}") not in ("0", "")]
    lux = [c for c in classes if c in LUX]
    if not lux or not norm or len(norm) < 4 or len(norm) > 32 or GENERIC.search(norm): continue
    filed = g("Filed")
    if not filed or filed > "1980": continue
    cands.append(dict(tm=g("Trade Mark"), mark=text, norm=norm, owner=owner, region=g("Region"), country=g("Country"), postcode=g("Postcode"),
                      status=st, filed=filed, registered=g("Registered"), expired=g("Expired") or g("Renewal Due Date"), lux=lux, type=g("Mark Type")))
by = {}
for c in cands:
    if c["norm"] in live_text: continue
    c["ownerLiveMarks"] = owner_live[c["owner"].lower()]
    core = [w for w in c["norm"].split() if w not in STOP]
    core = " ".join(core[:3])
    c["core"] = core
    if len(core) < 4 or core in live_grams or " ".join(core.split()[:2]) in live_grams: continue
    age = 2018 - int(c["filed"][:4])
    s = max(W[k] for k in c["lux"]) * 0.45 + min(age, 140) / 140 * 0.35 + (0.1 if c["type"] == "Word" else 0) + (0.1 if c["ownerLiveMarks"] == 0 else 0)
    if re.search(r"&|\bSONS\b|\bFRERES\b|\bCIE\b|\bMAISON\b|\bHOUSE OF\b|\bOF LONDON\b|\bLONDON\b|\bPARIS\b", c["norm"]): s += 0.08
    c["score"] = round(s, 4)
    k = c["norm"]
    if k not in by or by[k]["score"] < s:
        if k in by: c["lux"] = sorted(set(c["lux"]) | set(by[k]["lux"]))
        by[k] = c
pool = sorted(by.values(), key=lambda c: -c["score"])
cap = collections.Counter(); out = []
for c in pool:
    k = max(c["lux"], key=lambda x: W[x])
    if cap[k] >= 45: continue
    cap[k] += 1; out.append(c)
print(cap)
for c in out:
    c["classLabels"] = [LUX[k] for k in c["lux"]]
    c["tmNum"] = c["tm"].strip()
os.makedirs("../data-static", exist_ok=True)
json.dump({"source": "UK IPO Open Data: Domestic UK Applications (snapshot Feb 2018)", "licence": "OGL v3",
           "url": "https://www.gov.uk/government/publications/ipo-trade-mark-data-release", "candidates": len(cands), "marks": out},
          open("../data-static/sleeping-marks.json", "w"), ensure_ascii=False)
print(len(cands), len(out))
for c in out[:30]: print(c["filed"], c["expired"], c["mark"], "|", c["owner"], c["classLabels"], c["ownerLiveMarks"])

# Also record, for dormant-house names found on Wikidata, whether a live UK mark contained the name in Feb 2018.
try:
    import urllib.request, urllib.parse
    q = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "wikidata_dormant.rq")).read()
    req = urllib.request.Request("https://query.wikidata.org/sparql?" + urllib.parse.urlencode({"query": q}),
                                 headers={"Accept": "application/sparql-results+json", "User-Agent": "provenance-desk/1.0 (github.com/mhccog/provenance)"})
    if len(sys.argv) > 2:
        rows = json.load(open(sys.argv[2]))["results"]["bindings"]
    else:
        rows = json.load(urllib.request.urlopen(req, timeout=90))["results"]["bindings"]
    chk = {}
    for b in rows:
        lab = b.get("xLabel", {}).get("value", "")
        n = re.sub(r"[^A-Z0-9 ]", "", lab.upper()).strip()
        core = " ".join([w for w in n.split() if w not in STOP][:2])
        if core:
            chk[lab] = core in live_grams
    json.dump(chk, open("../data-static/tm-live-2018.json", "w"), ensure_ascii=False)
    print("wikidata names checked", len(chk), sum(chk.values()))
except Exception as e:
    print("wikidata check skipped", e)
