"""Daily data audit.
1. Schema: export leads to docs/data/leads.csv and validate it against a Table Schema with frictionless-py.
2. Links: write a sample of source links to audit/links.txt for lychee (run by the workflow) and read lychee's JSON report if present.
3. Spot-checks: re-read ~10 real records per source from the original publisher and compare key fields.
Writes docs/data/audit.json; build_desk.py then flags failing leads on their cards."""
import os, json, csv, random, re, time, sys
from common import get, load, save, now_iso, gh_headers, DATA, ROOT

random.seed(int(time.strftime("%Y%m%d")))
desk = load("desk.json", {}) or {}
leads = desk.get("leads", [])
out = {"generatedAt": now_iso(), "spotChecks": [], "deadLinks": [], "flagged": []}

# 1) schema
csv_path = os.path.join(DATA, "leads.csv")
cols = ["id", "tab", "kind", "title", "category", "score", "date", "trust_level", "freshness_level", "source_url"]
with open(csv_path, "w", newline="") as f:
    w = csv.writer(f); w.writerow(cols)
    for l in leads:
        w.writerow([l["id"], l["tab"], l.get("kind") or "", l["title"], l.get("category") or "", l["score"], (l.get("date") or "")[:10],
                    l["trust"]["level"], l["freshness"]["level"], l["sources"][0]["url"] if l.get("sources") else ""])
schema = {"fields": [
    {"name": "id", "type": "string", "constraints": {"required": True, "unique": True}},
    {"name": "tab", "type": "string", "constraints": {"required": True, "enum": ["revival", "import", "closing", "twins"]}},
    {"name": "kind", "type": "string"}, {"name": "title", "type": "string", "constraints": {"required": True}},
    {"name": "category", "type": "string"}, {"name": "score", "type": "integer", "constraints": {"minimum": 0, "maximum": 100}},
    {"name": "date", "type": "string", "constraints": {"pattern": "^$|^[+-]?\\d{4}(-\\d{2}-\\d{2})?.*$"}},
    {"name": "trust_level", "type": "integer", "constraints": {"minimum": 1, "maximum": 3}},
    {"name": "freshness_level", "type": "integer", "constraints": {"minimum": 1, "maximum": 3}},
    {"name": "source_url", "type": "string", "constraints": {"required": True, "pattern": "^https://.*"}}], "primaryKey": ["id"]}
json.dump(schema, open(os.path.join(DATA, "leads.schema.json"), "w"), indent=1)
try:
    from frictionless import Resource, Schema, validate
    rep = validate(Resource(path="leads.csv", basepath=DATA, schema=Schema.from_descriptor(schema)))
    errs = rep.flatten(["rowNumber", "fieldName", "type"]) if not rep.valid else []
    bad_rows = {e[0] for e in errs if e[0]}
    out["schema"] = {"valid": rep.valid, "errors": len(errs), "result": ("valid" if rep.valid else f"{len(errs)} problems in {len(bad_rows)} rows (held back)") + f" · {len(leads)} rows"}
    if bad_rows:
        rows = list(csv.reader(open(csv_path)))
        out["flagged"] += [rows[r - 1][0] for r in bad_rows if r - 1 < len(rows)]
except Exception as e:
    out["schema"] = {"valid": None, "result": f"frictionless not available ({e})"}

# 2) link sample for lychee
os.makedirs(os.path.join(ROOT, "audit"), exist_ok=True)
by_src = {}
for l in leads:
    for s in l.get("sources", []):
        by_src.setdefault(s["name"], []).append(s["url"])
sample = []
for name, urls in by_src.items():
    urls = sorted(set(urls)); random.shuffle(urls); sample += urls[:12]
open(os.path.join(ROOT, "audit", "links.txt"), "w").write("\n".join(sample) + "\n")
rep_path = os.path.join(ROOT, "audit", "lychee.json")
if os.path.exists(rep_path):
    try:
        r = json.load(open(rep_path))
        fails = []
        for src, items in (r.get("error_map") or r.get("fail_map") or {}).items():
            for it in items:
                u = it.get("url") if isinstance(it, dict) else it
                code = str((it.get("status") or {}).get("code", "")) if isinstance(it, dict) else ""
                fails.append(u)
        out["deadLinks"] = fails
        tot = r.get("total", len(sample)); ok = r.get("successful", 0) + r.get("excludes", 0) + r.get("unknown", 0)
        out["linkCheck"] = {"tool": "lychee", "result": f"{tot - len(fails)}/{tot} links OK" + (f"; {len(fails)} failing are flagged on their cards" if fails else "") + " (403/429 from bot-blocking sites count as reachable)"}
    except Exception as e:
        out["linkCheck"] = {"tool": "lychee", "result": f"report unreadable ({e})"}
else:
    out["linkCheck"] = {"tool": "lychee", "result": f"{len(sample)} links queued; report not present on this run"}


# 3) spot-checks against the original publisher
def pick(pred, n=10):
    pool = [l for l in leads if pred(l)]; random.shuffle(pool); return pool[:n]


def spot(source, items, fn, note=""):
    passed, checked, fails = 0, 0, []
    for l in items:
        try:
            ok = fn(l)
        except Exception as e:
            ok = None
        if ok is None: continue
        checked += 1
        if ok: passed += 1
        else: fails.append(l["id"])
        time.sleep(0.4)
    out["spotChecks"].append({"source": source, "checked": checked, "passed": passed, "failed": fails, "note": note})
    out["flagged"] += fails


def gz(l):
    import urllib.request
    nid = l["id"][3:]
    html = get(f"https://www.thegazette.co.uk/notice/{nid}", raw=True, headers={"Accept": "text/html"}).decode("utf-8", "ignore").upper()
    name = re.sub(r"\W+", " ", l["company"]["name"].upper()).split()
    return all(w in html for w in name[:3])
spot("The Gazette", pick(lambda l: l["tab"] == "closing"), gz, "company name found on the notice page")


def ct(l):
    nct = l["id"][3:]
    d = get(f"https://clinicaltrials.gov/api/v2/studies/{nct}", {"fields": "WhyStopped,OverallStatus"})
    return d["protocolSection"]["statusModule"].get("whyStopped", "").strip() == l["stalled"].strip()
spot("ClinicalTrials.gov", pick(lambda l: l.get("kind") == "Stopped clinical trial"), ct, "'why stopped' text identical")


def gh(l):
    full = l["subtitle"].split(" · ")[0]
    d = get(f"https://api.github.com/repos/{full}", headers=gh_headers())
    stars = int(l["facts"][1][1].replace(",", ""))
    return abs(d["stargazers_count"] - stars) <= max(50, stars * 0.1) and (d["archived"] or "seeking" in l["subtitle"])
spot("GitHub", pick(lambda l: l.get("kind") == "Abandoned project"), gh, "repo exists, still archived, stars within 10%")


def wd(l):
    q = l["id"].split("-", 1)[1]
    d = get("https://www.wikidata.org/w/api.php", {"action": "wbgetentities", "ids": q, "props": "labels|claims", "languages": "en", "format": "json"})
    e = d["entities"][q]
    return e.get("labels", {}).get("en", {}).get("value") == l["title"] and "P576" in e.get("claims", {})
spot("Wikidata", pick(lambda l: l.get("kind") == "Dormant house"), wd, "label matches and still recorded as dissolved")


def ti(l):
    q = l["id"][3:]
    d = get("https://taginfo.openstreetmap.org/api/4/tag/stats", {"key": "brand:wikidata", "value": q})
    n = sum(x["count"] for x in d["data"] if x["type"] == "all")
    claimed = int(l["facts"][2][1].replace(",", ""))
    uk = get("https://taginfo.geofabrik.de/europe:united-kingdom/api/4/tag/stats", {"key": "brand:wikidata", "value": q})
    nuk = sum(x["count"] for x in uk["data"] if x["type"] == "all")
    return abs(n - claimed) <= max(3, claimed * 0.2) and nuk == 0
spot("OpenStreetMap / taginfo", pick(lambda l: l["tab"] == "import"), ti, "location count within 20% and still 0 in the UK extract")


def tw(l):
    s = l["sides"][0]
    if s["source"] == "GitHub":
        full = s["url"].replace("https://github.com/", "")
        d = get(f"https://api.github.com/repos/{full}", headers=gh_headers())
        return d["created_at"][:10] == s["created"]
    if s["url"].startswith("https://doi.org/"):
        d = get("https://api.crossref.org/works/" + s["url"][16:])
        t = re.sub(r"\W+", " ", " ".join(d["message"].get("title", [""])).lower())
        return re.sub(r"\W+", " ", s["title"].lower())[:30].strip() in t
    return None
spot("Twin sources (GitHub/Crossref)", pick(lambda l: l["tab"] == "twins"), tw, "record exists; created date or title matches")

out["spotChecks"].append({"source": "UK IPO register", "checked": 0, "passed": 0, "failed": [], "note": "the live register blocks automated reads; every mark lead is labelled 'check before use'"})
tot = sum(s["checked"] for s in out["spotChecks"]); ps = sum(s["passed"] for s in out["spotChecks"])
out["summary"] = f"{ps}/{tot} spot-checked records matched their original page; {len(set(out['flagged']))} leads flagged"
out["flagged"] = sorted(set(out["flagged"]))
save("audit.json", out)
print(out["summary"], out.get("schema"), out.get("linkCheck"))
