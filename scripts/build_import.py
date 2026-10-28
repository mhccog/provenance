"""Import scout: luxury, craft and hospitality brands thriving abroad with no mapped UK presence.
Sources: OpenStreetMap name-suggestion-index (BSD-3, curated brand list with where each brand trades),
OSM taginfo (ODbL; worldwide count of mapped locations per brand), Geofabrik UK taginfo (ODbL; UK presence check),
Wikidata (CC0; descriptions, founding year, official website)."""
import os, re, json, time, math, urllib.parse
from common import overpass, get, save, load, clean, now_iso, STATIC, DATA

PATHS = {  # NSI path: (UK-facing category, luxury weight)
 "shop/jewelry": ("Jewellery", 1.0), "shop/watches": ("Watches", 1.0), "shop/perfumery": ("Perfume house", .95), "shop/pastry": ("Pâtisserie", .9),
 "shop/chocolate": ("Chocolatier", .9), "shop/confectionery": ("Confectioner", .7), "shop/tea": ("Tea house", .85), "shop/coffee": ("Coffee roaster", .7),
 "shop/wine": ("Wine merchant", .85), "shop/alcohol": ("Spirits & wine", .6), "shop/cheese": ("Cheese & fine food", .8), "shop/deli": ("Fine food", .75),
 "shop/leather": ("Leather goods", .95), "shop/bag": ("Bags & leather", .85), "shop/fashion_accessories": ("Accessories", .75), "shop/clothes": ("Fashion", .6),
 "shop/shoes": ("Shoemaker", .6), "shop/cosmetics": ("Beauty", .6), "shop/interior_decoration": ("Interiors", .8), "shop/furniture": ("Furniture & design", .55),
 "shop/houseware": ("Homeware", .55), "shop/household_linen": ("Fine linen", .8), "shop/candles": ("Candles & scent", .75), "shop/art": ("Art", .8),
 "shop/pottery": ("Ceramics", .85), "shop/craft": ("Craft", .7), "shop/department_store": ("Department store", .7), "tourism/hotel": ("Hotel concept", .95),
 "amenity/restaurant": ("Restaurant concept", .7), "amenity/cafe": ("Café concept", .65), "amenity/ice_cream": ("Gelato & ice cream", .7),
 "amenity/bar": ("Bar concept", .7), "leisure/sauna": ("Bathhouse & sauna", .9), "shop/bakery": ("Bakery", .6), "shop/musical_instrument": ("Instruments", .7),
 "shop/camera": ("Camera & optics", .6), "shop/hifi": ("Hi-fi", .7), "shop/boat": ("Boats", .9), "shop/florist": ("Florist", .6), "shop/beauty": ("Spa & beauty", .55),
}
MASS = re.compile(r"economy|budget|midscale|mid-scale|extended[- ]stay|discount|low[- ]cost|run by (Marriott|Hilton|Wyndham|IHG|Accor|Choice)|by (Marriott|Hilton|Wyndham|IHG|Accor|Choice)|owned by Wyndham|Inn & Suites|motel|supermarket|convenience|fast food|operated by Sterling|outlet|franchise of|of AccorHotels|Huazhu|Jin Jiang|budget hotel|hostel", re.I)
STRICT = re.compile(r"luxur|haute|premium|high-end|upscale|boutique|artisan|maison|heritage|patisser|chocolatier|perfumer|fragrance house|tea house|ryokan|onsen|design hotel|gelat|caviar|truffle|champagne|craft|atelier|couture|jewel(l)?er since|watchmaker|porcelain|silversmith|goldsmith|gourmet|fine food|confiserie|historic", re.I)
LUX = re.compile(r"luxur|haute|premium|high-end|upscale|fine|maison|patisser|chocolat|perfum|fragranc|jewel|watch|boutique|artisan|craft|heritage|design|porcelain|silver|gold|leather|couture|tailor|tea|gelat|wine|champagne|caviar|spa|bath|onsen|ryokan|sauna|hotel|resort|gourmet", re.I)
UK = {"gb", "uk", "001", "150", "155", "154", "gb-eng", "gb-sct", "gb-wls", "gb-nir", "eu"}
status = {}


def load_nsi():
    base = "https://cdn.jsdelivr.net/npm/name-suggestion-index@latest/dist/"
    nsi = get(base + "json/nsi.min.json", timeout=120)["nsi"]
    wd = get(base + "wikidata/wikidata.min.json", timeout=120)["wikidata"]
    return nsi, wd


def taginfo_counts():
    counts = {}
    for page in range(1, 30):
        d = get("https://taginfo.openstreetmap.org/api/4/key/values", {"key": "brand:wikidata", "sortname": "count", "sortorder": "desc", "rp": 999, "page": page})
        for v in d["data"]:
            counts[v["value"]] = v["count"]
        if len(d["data"]) < 999 or d["data"][-1]["count"] < 4: break
        time.sleep(0.5)
    return counts


UKTI = "https://taginfo.geofabrik.de/europe:united-kingdom/api/4/"


def uk_check(qids, names):
    """UK presence from Geofabrik's UK taginfo (OSM UK extract, refreshed daily): brand:wikidata, brand and exact name."""
    def allvals(key):
        vals = {}
        for page in range(1, 40):
            d = get(UKTI + "key/values", {"key": key, "rp": 999, "page": page, "sortname": "count", "sortorder": "desc"})
            for v in d["data"]: vals[v["value"]] = v["count"]
            if len(d["data"]) < 999: break
            time.sleep(0.3)
        return vals, d.get("data_until")
    wd_uk, until = allvals("brand:wikidata")
    brand_uk, _ = allvals("brand")
    brand_lc = {k.lower(): v for k, v in brand_uk.items()}
    present = {q: wd_uk[q] for q in qids if q in wd_uk}
    byname = {}
    for n in names:
        if not n: continue
        c = brand_lc.get(n.lower(), 0)
        if not c:
            try:
                d = get(UKTI + "key/values", {"key": "name", "query": n, "rp": 50, "page": 1})
                c = sum(v["count"] for v in d["data"] if v["value"].lower() == n.lower())
            except Exception:
                c = 0
            time.sleep(0.15)
        if c: byname[n] = c
    return present, byname, until


def centroids():
    g = json.load(open(os.path.join(DATA, "countries.geojson")))
    return {f["properties"]["a2"].lower(): (f["properties"]["ly"], f["properties"]["lx"], f["properties"]["n"]) for f in g["features"]}


def main():
    try:
        nsi, wd = load_nsi()
        counts = taginfo_counts()
    except Exception as e:
        print("import scout failed", e)
        old = load("import.json", {}) or {}
        save("import.json", {"generatedAt": old.get("generatedAt"), "status": {"ok": False, "error": str(e), "note": "kept previous leads"}, "leads": old.get("leads", [])})
        return
    status.update({"nsiBrands": 0, "taginfoValues": len(counts)})
    uk_q = set()
    cands = {}
    for path, tree in nsi.items():
        if not path.startswith("brands/"): continue
        for it in tree.get("items", []):
            q = it.get("tags", {}).get("brand:wikidata")
            if not q: continue
            inc = [str(x).lower() for x in it.get("locationSet", {}).get("include", [])]
            if any(x in UK or x.startswith("gb") for x in inc):
                uk_q.add(q)
    for path, tree in nsi.items():
        p = path.replace("brands/", "")
        if p not in PATHS: continue
        for it in tree.get("items", []):
            q = it.get("tags", {}).get("brand:wikidata")
            if not q or q in uk_q: continue
            inc = [str(x).lower() for x in it.get("locationSet", {}).get("include", []) if isinstance(x, str)]
            n = counts.get(q, 0)
            if n < 3: continue
            w = wd.get(q, {})
            desc = w.get("description", "")
            if MASS.search(desc + " " + (it.get("displayName") or "")) or n > 900: continue
            cat, lw = PATHS[p]
            lux = bool(LUX.search(desc + " " + it.get("displayName", "")))
            strict = bool(STRICT.search(desc + " " + it.get("displayName", "")))
            v = lw * (1.0 if strict else 0.85 if lux else 0.7)
            # sweet spot: proven (10+ sites) but still exclusive (under ~300); giant chains score lower
            score_n = min(1, math.log10(n + 1) / 2.2) * (1.0 if n <= 300 else 0.75 if n <= 600 else 0.55)
            nm = it.get("displayName") or it["tags"].get("brand") or ""
            en = it["tags"].get("brand:en") or it["tags"].get("name:en") or w.get("label")
            if en and not re.search(r"[A-Za-z]", nm): nm = f"{en} ({nm})"
            cands[q] = {"q": q, "name": nm, "match": it.get("displayName") or it["tags"].get("brand"), "strict": strict, "path": p, "cat": cat, "where": inc, "n": n,
                        "desc": desc, "site": (w.get("officialWebsites") or [None])[0] or w.get("identities", {}).get("website"),
                        "logo": (w.get("logos") or {}).get("wikidata"), "lux": lux, "v": v, "sn": score_n,
                        "pre": v * 0.6 + score_n * 0.4}
    status["candidates"] = len(cands)
    pool = sorted(cands.values(), key=lambda c: -c["pre"])
    top, capn = [], {}
    for c in pool:
        if capn.get(c["cat"], 0) >= 30: continue
        capn[c["cat"]] = capn.get(c["cat"], 0) + 1; top.append(c)
        if len(top) >= 320: break
    try:
        present, byname, until = uk_check([c["q"] for c in top], [c["match"] for c in top])
        status["ukCheck"] = f"Geofabrik UK taginfo (OSM data until {until}): brand:wikidata, brand and exact-name check"
    except Exception as e:
        print("overpass failed", e)
        old = load("import.json", {}) or {}
        save("import.json", {"generatedAt": old.get("generatedAt"), "status": {"ok": False, "error": "UK check unavailable: " + str(e), "note": "kept previous leads"}, "leads": old.get("leads", [])})
        return
    cen = centroids()
    out = []
    for c in top:
        if present.get(c["q"]) or byname.get(c["match"]): continue
        countries = [x for x in c["where"] if len(x) == 2]
        where = ", ".join(cen.get(x, (0, 0, x.upper()))[2] for x in countries[:4]) or "several countries"
        place = None
        if countries and countries[0] in cen:
            la, lo, nm = cen[countries[0]]
            place = {"lat": la, "lon": lo, "label": nm + " (country)", "precision": "country"}
        out.append({
            "id": "im-" + c["q"], "tab": "import", "kind": c["cat"], "title": c["name"],
            "subtitle": f"{c['cat']} · thriving in {where}",
            "date": None, "dateLabel": "",
            "facts": [["What it is", clean(c["desc"]) or "(no Wikidata description)"], ["Where it trades", where],
                      ["Mapped locations worldwide (OSM)", f"{c['n']:,}"], ["UK locations found", "0 mapped by brand or exact name"],
                      ["Official site", c["site"] or "-"]],
            "evidence": f"{c['n']:,} locations mapped on OpenStreetMap under this brand, all outside the UK.",
            "gap": "No UK location tagged with this brand or exact name in OpenStreetMap's UK data (checked today). It may still sell online or through UK stockists, so check before pitching.",
            "category": c["cat"], "luxury": c["strict"], "place": place, "logo": c["logo"],
            "who": [f"UK operators in {c['cat'].lower()} looking for a new concept (franchise or licence)", "Luxury department stores and food halls (concessions, pop-ups)", "Property owners with prime retail units in Mayfair, Marylebone, Chelsea, Edinburgh New Town"],
            "deal": "Act as UK agent: introduce the brand to a master franchisee, landlord or department store; agent's commission or a retained fee on signing.",
            "sources": [{"name": "OpenStreetMap name-suggestion-index", "url": f"https://nsi.guide/?id={urllib.parse.quote(c['q'])}", "licence": "BSD-3 (index), ODbL (OSM data)", "trust": "community"},
                        {"name": "Wikidata", "url": f"https://www.wikidata.org/wiki/{c['q']}", "licence": "CC0", "trust": "community"},
                        {"name": "taginfo (location count)", "url": f"https://taginfo.openstreetmap.org/tags/brand:wikidata={c['q']}", "licence": "ODbL", "trust": "community"}],
            "scoreParts": {"value": round(c["v"], 3), "fresh": round(c["sn"], 3), "fit": 0.95 if c["strict"] else 0.75 if c["lux"] else 0.5},
            "site": c["site"],
        })
    status.update({"ok": True, "leads": len(out), "checkedInUK": len(top)})
    save("import.json", {"generatedAt": now_iso(), "status": status, "leads": out})


if __name__ == "__main__":
    main()
