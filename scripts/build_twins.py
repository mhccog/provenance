"""Twin finder: people building the same rare thing in different countries who show no sign of knowing each other.
A) Reuses 'You're not the only one' (mhccog/not-the-only-one) weekly convergences (OpenAlex, GitHub, HN, arXiv), keeping
   cross-country pairs and checking for cross-citation via Crossref open references.
B) Own daily sweep of maker / craft / luxury topics on GitHub (public repo + owner profile metadata), grouped with the
   same TF-IDF word-overlap idea, owners placed via their public profile location (Photon/OSM geocoder)."""
import os, re, json, time, math, datetime, itertools, urllib.parse, collections
from common import get, save, load, clean, fresh, days_ago, now_iso, gh_headers, TODAY, STATIC

TOPICS = [
 ("Mechanical & open-source watches", "watch movement"), ("Fragrance formulation", "perfume"), ("Espresso machine mods", "espresso machine"),
 ("Looms & weaving", "loom weaving"), ("Knitting machines", "knitting machine"), ("Sewing & tailoring patterns", "sewing pattern"),
 ("Leathercraft", "leather"), ("Ceramic glazes", "glaze ceramic"), ("Luthiery & guitar building", "guitar luthier"),
 ("Analog film cameras", "film camera"), ("Type design", "typeface font design"), ("Bookbinding & letterpress", "letterpress"),
 ("Cocktail machines", "cocktail machine"), ("Winemaking & fermentation", "fermentation wine"), ("Beekeeping tech", "beehive"),
 ("Yacht & sailing autopilots", "sailboat autopilot"), ("Jewellery design (parametric)", "jewelry design"), ("Fountain pens & ink", "fountain pen"),
 ("Hi-fi & valve amplifiers", "tube amplifier"), ("Mechanical keyboards (boutique)", "keyboard pcb"), ("Bread & pâtisserie science", "sourdough"),
 ("Chocolate making", "chocolate tempering"), ("Coffee roasting", "coffee roaster"), ("Embroidery machines", "embroidery"),
]
STOP = set("a an the and or for of to in on with by from is are be this that it as at your you our we using use based open source project simple tool app made make your my".split())
geo_cache = load("geo-cache.json", {}, static=True) or {}
status = {}
JUNK = re.compile(r"website|web site|landing|clone|portfolio|assignment|homework|course|tutorial|bootcamp|e-?commerce|shop website|template|dashboard ui|my first|practice|student|internship|hackathon", re.I)


def toks(s):
    return [w for w in re.findall(r"[a-z][a-z0-9\-]{2,}", (s or "").lower()) if w not in STOP]


def geocode(loc):
    if not loc: return None
    k = loc.strip().lower()[:80]
    if k in geo_cache: return geo_cache[k]
    try:
        d = get("https://photon.komoot.io/api/", {"q": loc, "limit": 1, "lang": "en"}, tries=2, timeout=30)
        f = (d.get("features") or [None])[0]
        r = None
        if f:
            p = f["properties"]; lon, lat = f["geometry"]["coordinates"]
            r = {"lat": round(lat, 3), "lon": round(lon, 3), "city": p.get("city") or (p.get("name") if p.get("type") in ("city", "town", "village") else None),
                 "country": (p.get("countrycode") or "").upper(), "countryName": p.get("country"), "precision": "country" if p.get("type") == "country" else "city"}
        geo_cache[k] = r
        time.sleep(1.0)
        return r
    except Exception:
        return None


def sweep():
    since = (TODAY - datetime.timedelta(days=730)).isoformat()
    pairs = []
    users = {}
    for label, q in TOPICS:
        try:
            d = get("https://api.github.com/search/repositories", {"q": f"{q} in:name,description,topics created:>{since} stars:>=2 fork:false", "sort": "stars", "per_page": 50}, headers=gh_headers())
        except Exception as e:
            print("search", q, e); continue
        time.sleep(2.2)
        repos = [r for r in d.get("items", []) if r.get("description") and not JUNK.search(r["name"] + " " + r["description"])]
        docs = []
        for r in repos:
            t = toks(r["name"].replace("-", " ") + " " + r["description"] + " " + " ".join(r.get("topics", [])))
            docs.append(t)
        df = collections.Counter(w for t in docs for w in set(t))
        N = len(docs) or 1
        vec = []
        for t in docs:
            tf = collections.Counter(t)
            v = {w: (c / len(t)) * math.log((N + 1) / (df[w] + 0.5)) for w, c in tf.items()} if t else {}
            norm = math.sqrt(sum(x * x for x in v.values())) or 1
            vec.append({w: x / norm for w, x in v.items()})
        for i, j in itertools.combinations(range(len(repos)), 2):
            a, b = repos[i], repos[j]
            if a["owner"]["login"].lower() == b["owner"]["login"].lower(): continue
            sim = sum(vec[i].get(w, 0) * vec[j].get(w, 0) for w in vec[i])
            if sim < 0.16: continue
            if abs(days_ago(a["created_at"]) - days_ago(b["created_at"])) > 540: continue
            shared = sorted(set(vec[i]) & set(vec[j]), key=lambda w: -(vec[i][w] * vec[j][w]))[:5]
            pairs.append((sim, label, a, b, shared))
    pairs.sort(key=lambda p: -p[0])
    out, used = [], collections.Counter()
    for sim, label, a, b, shared in pairs:
        if used[a["full_name"]] >= 2 or used[b["full_name"]] >= 2: continue
        sides = []
        for r in (a, b):
            lg = r["owner"]["login"]
            if lg not in users:
                try:
                    u = get(f"https://api.github.com/users/{lg}", headers=gh_headers(), tries=2)
                    users[lg] = {"type": u.get("type"), "location": u.get("location"), "blog": u.get("blog"), "company": u.get("company"), "followers": u.get("followers", 0), "name": u.get("name")}
                except Exception:
                    users[lg] = {}
            u = users[lg]
            sides.append({"title": r["name"], "url": r["html_url"], "desc": clean(r["description"], 180), "by": u.get("name") or lg, "handle": lg, "ownerType": u.get("type"),
                          "stars": r["stargazers_count"], "created": r["created_at"][:10], "place": geocode(u.get("location")), "locationText": u.get("location"),
                          "site": u.get("blog") or None, "source": "GitHub"})
        pa, pb = sides[0]["place"], sides[1]["place"]
        if not pa or not pb or not pa.get("country") or pa.get("country") == pb.get("country"): continue
        # do they know each other? (follow/star link is too costly; use mention check in READMEs is skipped) - check if either repo description mentions the other
        mention = sides[1]["handle"].lower() in (sides[0]["desc"] or "").lower() or sides[0]["handle"].lower() in (sides[1]["desc"] or "").lower()
        if mention: continue
        used[a["full_name"]] += 1; used[b["full_name"]] += 1
        small = all(s["ownerType"] == "User" or s["stars"] < 500 for s in sides)
        out.append(mk_lead("tw-" + str(a["id"]) + "-" + str(b["id"]), label, sides, shared, sim, "GitHub sweep (maker & craft topics)", small, None))
    json.dump(geo_cache, open(os.path.join(STATIC, "geo-cache.json"), "w"))
    status["sweep"] = {"ok": True, "pairsConsidered": len(pairs), "n": len(out)}
    return out


def mk_lead(lid, topic, sides, shared, sim, origin, small, citeCheck, academic=False):
    a, b = sides
    la = (a["place"] or {}); lb = (b["place"] or {})
    where = f"{la.get('city') or la.get('countryName') or la.get('country')} ↔ {lb.get('city') or lb.get('countryName') or lb.get('country')}"
    newest = max(a.get("created") or "", b.get("created") or "")
    return {
        "id": lid, "tab": "twins", "kind": "Research twins" if academic else "Maker twins", "title": (f"{short(a['title'])} × {short(b['title'])}"), "subtitle": f"{topic} · {where}",
        "date": newest, "dateLabel": "newest side started",
        "sides": sides, "overlap": shared, "similarity": round(sim, 3), "origin": origin,
        "facts": [["Shared terms", ", ".join(shared) or "-"], ["Similarity (TF-IDF cosine)", f"{sim:.2f}"], ["Countries", where],
                  ["Cross-citation / mention", citeCheck or "No mention of each other in their public descriptions"], ["Small teams", "yes" if small else "at least one larger team"]],
        "category": topic, "luxury": bool(re.search(r"watch|perfum|fragranc|jewel|leather|tailor|loom|weav|luthier|type|letterpress|pen|chocolate|wine|cocktail|yacht|sail|valve|tube|ceramic|glaze|espresso|coffee|pâtisserie|sourdough|embroider|knit|camera", topic, re.I)),
        "place": a["place"], "place2": b["place"],
        "why": "Two independent makers on the same rare problem: together they halve the work, share suppliers, and become the obvious name in a tiny niche.",
        "deal": "Introduce them (with each one's consent), then propose a joint collection, shared tooling or a pop-up/event you organise; matchmaking fee, a small stake in a joint venture, or ticketed event revenue.",
        "who": [f"{a['by']} ({(a['place'] or {}).get('countryName') or ''})", f"{b['by']} ({(b['place'] or {}).get('countryName') or ''})"],
        "sources": [{"name": s["source"], "url": s["url"], "licence": "public metadata", "trust": "platform" if s["source"] == "GitHub" else ("academic" if s["source"] in ("OpenAlex", "arXiv") else "community")} for s in sides],
        "scoreParts": {"value": (0.5 if academic else 0.8) * (1 if small else 0.75), "fresh": round(fresh(newest, 120), 3), "fit": round(min(1, sim * 2), 3)},
    }


def short(t, n=46):
    t = re.sub(r"\s+", " ", t or "").strip()
    return t if len(t) <= n else t[: n - 1].rsplit(" ", 1)[0] + "…"


def crossref_refs(doi):
    try:
        d = get(f"https://api.crossref.org/works/{urllib.parse.quote(doi)}", {"mailto": "noreply@users.noreply.github.com"}, tries=2, timeout=30)
        return {(r.get("DOI") or "").lower() for r in d["message"].get("reference", []) if r.get("DOI")}, bool(d["message"].get("reference"))
    except Exception:
        return set(), False


def reused():
    try:
        d = get("https://mhccog.github.io/not-the-only-one/data/discoveries.json", timeout=60)
    except Exception as e:
        status["reused"] = {"ok": False, "error": str(e)}; return []
    out = []
    for t in d.get("topics", []):
        for c in t.get("convergences", []):
            for a, b in itertools.combinations(c["members"], 2):
                pa, pb = a.get("place") or {}, b.get("place") or {}
                if not pa.get("country") or not pb.get("country") or pa["country"] == pb["country"]: continue
                small = (a.get("nAuthors") or 1) <= 6 and (b.get("nAuthors") or 1) <= 6
                cite = None
                if a["source"] == "openalex" and b["source"] == "openalex":
                    da = a["url"].replace("https://doi.org/", "").lower(); db = b["url"].replace("https://doi.org/", "").lower()
                    ra, oka = crossref_refs(da); rb, okb = crossref_refs(db)
                    if db in ra or da in rb: continue
                    cite = "Neither cites the other (Crossref open references)" if (oka or okb) else "Citation lists not open on Crossref: not checked"
                    time.sleep(0.3)
                sides = [{"title": clean(m["title"], 110), "url": m["url"], "desc": m.get("venue") or m.get("kind"), "by": m.get("by"), "handle": None,
                          "ownerType": None, "stars": None, "created": m.get("date"), "place": {**m["place"], "precision": m["place"].get("precision")},
                          "locationText": m["place"].get("label"), "site": None, "source": m.get("sourceLabel") or m["source"]} for m in (a, b)]
                out.append(mk_lead("nto-" + re.sub(r"\W", "", a["id"] + b["id"])[:60], t["topic"], sides, c.get("terms", []), c.get("cohesion", 0.3) + 0.1,
                                   "Reused from 'You're not the only one'", small, cite, academic=True))
                break
    status["reused"] = {"ok": True, "n": len(out), "generatedAt": d.get("generatedAt")}
    return out


def main():
    leads = []
    for fn in (sweep, reused):
        try:
            leads += fn()
        except Exception as e:
            print(fn.__name__, e); status[fn.__name__] = {"ok": False, "error": str(e)}
    save("twins.json", {"generatedAt": now_iso(), "status": status, "leads": leads})


if __name__ == "__main__":
    main()
