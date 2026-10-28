"""Closing-down treasure hunter.
Source: The Gazette (official public record, OGL v3) corporate insolvency notices.
For each recent notice we read the notice's own linked data (company number, nature of business
as published, postcode with lat/long, insolvency practitioner as published) and flag sectors
likely to hold unusual, high-appeal physical assets. Nearby buyers come from OpenStreetMap (ODbL)."""
import os, re, time, json, datetime
from common import overpass, get, save, load, clean, fresh, days_ago, now_iso, TODAY

DAYS = int(os.environ.get("CLOSING_DAYS", "21"))
TYPES = {"2410": "Administrator appointed", "2432": "Liquidator appointed",
         "2452": "Winding-up order", "2431": "Resolution to wind up"}
G = "https://www.thegazette.co.uk"
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data-static", "gazette-cache.json")

# category: (keywords in nature of business / SIC text / name, appeal 1-5, likely assets, likely buyers, OSM tags for nearby buyers)
CATS = [
 ("Vineyard, distillery & brewery", r"distill|spirit|gin\b|whisk|vineyard|winer|wine produc|manufacture of wine|brew|beer|cider|malt", 5,
  "stills, fermenters, casks, bottling lines, aged stock, brand and recipes", "craft distillers, brewers and drinks start-ups", ['craft=distillery','craft=brewery','craft=winery']),
 ("Hotel & country house", r"hotel|country house|guest house|\binn\b|resort|holiday centre|accommodation", 5,
  "furniture, antiques, art, linen, kitchen kit, the hotel name and booking list", "boutique hotel groups, antique dealers, interior designers", ['tourism=hotel']),
 ("Jeweller & watchmaker", r"\bjewel|\bwatch(es|maker|making)?\b|\bclocks?\b|goldsmith|silversmith|precious metal|diamond|\bgems?\b|gemstone|horolog", 5,
  "workbenches, tools, stock, display cases, brand", "independent jewellers and bench jewellers", ['shop=jewelry','craft=jeweller','shop=watches']),
 ("Couture, tailoring & leather", r"tailor|couture|bespoke|dressmak|leather|saddl|millin|shoe|footwear|textile|knit|weav|fashion|apparel|clothing|wearing apparel", 4,
  "industrial sewing machines, cutting tables, patterns, fabric and leather stock, label", "independent tailors, fashion labels, costume houses", ['craft=tailor','shop=tailor','craft=dressmaker','craft=shoemaker','shop=fabric']),
 ("Classic car, coachbuilding & motorsport", r"coachbuild|classic car|vintage car|restoration of (motor|vehic)|motorsport|racing|manufacture of motor vehicles|bodies \(coachwork\)|car body", 5,
  "lifts, paint booth, panel tools, parts stock, project cars", "restoration specialists, collectors, motorsport teams", ['shop=car_repair','craft=coachbuilder']),
 ("Boat & yacht builder", r"boat|yacht|\bmarine?\b|marina|shipbuild|ship repair|sailing|chandler", 5,
  "moulds, hulls, marine engines, chandlery stock, boatyard kit", "boatyards, marinas, marine engineers", ['craft=boatbuilder','leisure=marina','shop=boat']),
 ("Gallery, art & antiques", r"galler|antique|art dealer|fine art|auction|artist|frame|framing|sculpt", 5,
  "artworks, antiques, hanging systems, framing kit, client lists (as assets only)", "dealers, auction houses, interior designers", ['shop=art','shop=antiques','tourism=gallery']),
 ("Fine dining & restaurant", r"restaurant|licensed|catering|bar\b|bars|cafe|patisser|chocolat|bakery|bakeries|confection|deli", 3,
  "commercial kitchen (ovens, extraction, cold rooms), furniture, wine stock", "restaurant groups, chefs opening sites, dark kitchens", ['amenity=restaurant']),
 ("Film, music & studio kit", r"film|motion picture|video|television|recording|sound|music|photograph|studio|broadcast|post-production|lighting|theatre|performing arts", 4,
  "cameras, lenses, lighting, sound desks, sets and props", "production companies, rental houses, film schools", ['amenity=studio','craft=photographer']),
 ("Equestrian & rural", r"equestr|horse|\bstud\b|stables|riding|livery|\bpolo\b|racehorse|farm|agricultur|country estate|sporting estate", 4,
  "tack, horseboxes, arena kit, farm machinery, land-based stock", "yards, studs, farms and rural estates", ['leisure=horse_riding','shop=equestrian']),
 ("Lab & science", r"laborator|research and experimental|biotech|pharmaceut|scientific|testing and analysis|medical device|optical", 4,
  "lab benches, fume cupboards, freezers, analytical instruments", "university spin-outs, biotech start-ups, school labs", ['office=research']),
 ("Workshop, making & print", r"joinery|furniture|cabinet|woodwork|metal|forg|foundry|engineering|machin|fabricat|print|ceramic|pottery|glass|upholster|signs|3d", 3,
  "machine tools, CNC, kilns, presses, presses, material stock", "makers, workshops, design studios", ['craft=carpenter','craft=metal_construction','shop=furniture']),
 ("Gym & wellness", r"gym|fitness|sport|leisure|spa\b|spas\b|beauty|salon|yoga|pilates|climbing", 2,
  "gym equipment, spa fit-out, salon chairs", "independent gyms and studios", ['leisure=fitness_centre']),
]
LAPPEAL = {5: "very high", 4: "high", 3: "medium", 2: "modest", 1: "low"}


def list_notices():
    start = (TODAY - datetime.timedelta(days=DAYS)).isoformat()
    out = []
    for code in TYPES:
        page = 1
        while page <= 30:
            d = get(G + "/insolvency/notice/data.json", {"noticetypes": code, "start-publish-date": start,
                                                          "results-page-size": 100, "results-page": page})
            es = d.get("entry") or []
            if isinstance(es, dict): es = [es]
            for e in es:
                out.append((code, e))
            if len(es) < 100: break
            page += 1
            time.sleep(0.4)
    return out


def first(x):
    return x[0] if isinstance(x, list) and x else x


def find_ips(obj):
    ips = []
    def walk(o):
        if isinstance(o, dict):
            if "hasIPnum" in o or ("_about" in o and "insolvency-practitioner" in str(o.get("_about"))):
                if o.get("name"):
                    ip = {}
                    for k in ("name", "hasIPnum", "email", "telephone"):
                        v = o.get(k)
                        if isinstance(v, list): v = v[0] if v else None
                        if v: ip[k] = str(v)
                    ips.append(ip)
            for v in o.values(): walk(v)
        elif isinstance(o, list):
            for v in o: walk(v)
    walk(obj)
    seen, res = set(), []
    for ip in ips:
        k = str(ip.get("name") or "").lower()
        if k and k not in seen:
            seen.add(k); res.append(ip)
    return res


def find_key(obj, key):
    if isinstance(obj, dict):
        if key in obj: return obj[key]
        for v in obj.values():
            r = find_key(v, key)
            if r is not None: return r
    elif isinstance(obj, list):
        for v in obj:
            r = find_key(v, key)
            if r is not None: return r
    return None


def firm_from_content(text):
    m = re.search(r"(?:of|at)\s+([A-Z][A-Za-z&'.,\- ]{3,60}?(?:LLP|Limited|Ltd|Partners|Advisory|Recovery|Insolvency|Group))", text)
    return m.group(1).strip() if m else None


def classify(text):
    best = None
    for name, rx, appeal, assets, buyers, osm in CATS:
        if re.search(rx, text, re.I):
            if not best or appeal > best[2]:
                best = (name, rx, appeal, assets, buyers, osm)
    return best


def nearby(lat, lon, osm_tags, radius=30000):
    parts = []
    for t in osm_tags:
        k, v = t.split("=")
        parts.append(f'nwr["{k}"="{v}"]["name"](around:{radius},{lat},{lon});')
    q = f'[out:json][timeout:25];({"".join(parts)});out center 40;'
    try:
        d = overpass(q, timeout=45)
    except Exception as e:
        print("overpass fail", e); return None
    res = []
    for el in d.get("elements", []):
        tg = el.get("tags", {})
        la = el.get("lat") or (el.get("center") or {}).get("lat"); lo = el.get("lon") or (el.get("center") or {}).get("lon")
        res.append({"name": tg.get("name"), "kind": next((f"{k}={tg[k]}" for k in ("craft","shop","tourism","amenity","leisure","office") if k in tg), ""),
                    "web": tg.get("website") or tg.get("contact:website"), "osm": f"https://www.openstreetmap.org/{el['type']}/{el['id']}",
                    "km": round(((la - lat) ** 2 + ((lo - lon) * 0.62) ** 2) ** 0.5 * 111, 1) if la else None})
    res.sort(key=lambda r: r["km"] or 99)
    return res[:6]


def main():
    status = {"source": "The Gazette insolvency notices", "ok": True, "fetchedAt": now_iso()}
    try:
        notices = list_notices()
    except Exception as e:
        print("gazette list failed", e)
        save("closing.json", {"generatedAt": now_iso(), "status": {**status, "ok": False, "error": str(e)}, "leads": load("closing.json", {}).get("leads", [])})
        return
    print("notices", len(notices))
    cache = load("gazette-cache.json", {}, static=True) or {}
    leads, seen_co = [], set()
    n_fetch = 0
    from concurrent.futures import ThreadPoolExecutor

    def fetch_ld(item):
        code, e = item
        nid = e["id"].rsplit("/", 1)[-1]
        try:
            d = get(f"{G}/notice/{nid}/data.json?view=linked-data", timeout=40, tries=3)
        except Exception as ex:
            print("notice fail", nid, ex); return nid, None
        pt = d["result"]["primaryTopic"]
        about = pt.get("isAbout") or {}
        co = first(find_key(about, "company")) or {}
        if not isinstance(co, dict): co = {}
        pc = find_key(about, "postcode") or {}
        pc = first(pc) if isinstance(pc, list) else pc
        if not isinstance(pc, dict): pc = {}
        def s1(v):
            return (v[0] if isinstance(v, list) and v else v) if v else None
        area = pc.get("msg0_administrative_area")
        area = s1(area)
        addr = None
        for k in ("hasPrincipalTradingAddress", "hasRegisteredOffice"):
            a = s1(co.get(k))
            if isinstance(a, dict) and a.get("label"):
                addr = a["label"]; break
        return nid, {"address": addr, "company": s1(co.get("organisationName")), "number": s1(co.get("companyNumber")), "nature": s1(co.get("natureOfBusiness")),
                     "trading": s1(co.get("tradingAs")), "postcode": s1(pc.get("label")), "lat": s1(pc.get("lat")), "lon": s1(pc.get("long")),
                     "area": area.get("label") if isinstance(area, dict) else None, "ips": find_ips(about), "published": e.get("published", "")[:10]}

    todo = [(c, e) for c, e in notices if e["id"].rsplit("/", 1)[-1] not in cache]
    print("to fetch", len(todo))
    with ThreadPoolExecutor(max_workers=2) as ex:
        for i, (nid, ld) in enumerate(ex.map(fetch_ld, todo)):
            if ld: cache[nid] = ld; n_fetch += 1
            if i % 200 == 199:
                print("fetched", i + 1)
                with open(CACHE, "w") as f: json.dump(cache, f)
    with open(CACHE, "w") as f: json.dump(cache, f)
    for code, e in notices:
        nid = e["id"].rsplit("/", 1)[-1]
        title = clean(e.get("title"))
        content = clean(e.get("content"))
        ld = cache.get(nid)
        if not ld: continue
        name = ld.get("company") or title
        addr = ld.get("address")
        if not addr:
            m = re.search(r"(?:Principal trading address|Registered office|Registered Office)\s*:?\s*(.+?)(?:\s+(?:Principal trading|Date of|Nature of|Name of|Liquidator|Office Holder|Former|Company Number|Joint)|…|$)", content, re.I)
            addr = m.group(1).strip(" ,.") if m else None
        pcm = re.search(r"\b([A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2})\b", addr or "")
        town = None
        if addr:
            parts = [p.strip() for p in addr.split(",") if p.strip()]
            parts = [p for p in parts if not re.fullmatch(r"[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}", p)]
            town = parts[-1] if parts else None
            if town and re.search(r"shire$|^Greater |^West |^East |^North |^South ", town) and len(parts) > 1: town = parts[-2] + ", " + town
        key = (ld.get("number") or name).upper()
        text = " ".join(filter(None, [ld.get("nature"), name, ld.get("trading")]))
        cat = classify(text)
        if not cat or key in seen_co:
            continue
        seen_co.add(key)
        lat = ld.get("lat"); lon = ld.get("lon")
        if lat is None and e.get("geo:Point"):
            lat = float(e["geo:Point"]["geo:lat"]); lon = float(e["geo:Point"]["geo:long"])
        nature_hit = bool(ld.get("nature") and re.search(cat[1], ld["nature"], re.I))
        conf = "nature of business as published" if nature_hit else "company name only (nature of business not stated or not matching)"
        fit = 1.0 if nature_hit else 0.55
        leads.append({
            "id": "gz-" + nid, "tab": "closing", "title": name.title() if name.isupper() else name,
            "subtitle": f"{cat[0]} · {TYPES[code]} · {ld.get('area') or town or 'UK'}",
            "category": cat[0], "appeal": cat[2], "appealLabel": LAPPEAL[cat[2]],
            "date": ld.get("published") or e.get("published", "")[:10], "noticeType": TYPES[code],
            "company": {"name": name, "number": ld.get("number"), "nature": ld.get("nature"), "trading": ld.get("trading")},
            "place": {"lat": lat, "lon": lon, "label": ", ".join(filter(None, [ld.get("area") or town, ld.get("postcode") or (pcm.group(1) if pcm else None)])) or "address in notice", "precision": "notice geotag (may be the office-holder's address)"} if lat else None,
            "address": addr,
            "ips": ld.get("ips") or [], "firm": firm_from_content(content),
            "assets": cat[3], "buyers": cat[4], "osmTags": cat[5], "matchConfidence": conf, "excerpt": clean(content, 260),
            "sources": [{"name": "The Gazette", "url": f"{G}/notice/{nid}", "licence": "OGL v3", "trust": "official"}]
                       + ([{"name": "Companies House", "url": f"https://find-and-update.company-information.service.gov.uk/company/{ld['number']}", "licence": "OGL v3", "trust": "official"}] if ld.get("number") else []),
            "scoreParts": {"value": cat[2] / 5, "fresh": round(fresh(ld.get("published"), 14), 3), "fit": fit},
        })
    # tidy place names with postcodes.io reverse geocoding (OGL; ONS/Royal Mail derived)
    pts = [l for l in leads if l["place"]]
    for i in range(0, len(pts), 100):
        chunk = pts[i:i + 100]
        body = json.dumps({"geolocations": [{"longitude": l["place"]["lon"], "latitude": l["place"]["lat"], "limit": 1, "radius": 2000} for l in chunk]}).encode()
        try:
            d = get("https://api.postcodes.io/postcodes", data=body, headers={"Content-Type": "application/json"}, timeout=60)
            for l, r in zip(chunk, d.get("result", [])):
                res = (r.get("result") or [None])[0]
                if res:
                    dist = res.get("admin_district") or res.get("parish")
                    l["place"]["label"] = ", ".join(filter(None, [dist, res.get("region") or res.get("country")]))
                    l["place"]["district"] = dist
                    l["subtitle"] = f"{l['category']} · {l['noticeType']} · {dist or 'UK'}"
        except Exception as e:
            print("postcodes.io", e)
    for l in leads:
        if l["place"] and not l["place"].get("district"):
            l["subtitle"] = f"{l['category']} · {l['noticeType']} · UK"
        if l.get("address"):
            l["address"] = clean(re.split(r"\s+(?:In the High Court|Type of Liq|Date of|Nature of)", l["address"])[0], 140)
    # nearby buyers for the strongest leads
    leads.sort(key=lambda l: -(l["scoreParts"]["value"] * 0.5 + l["scoreParts"]["fresh"] * 0.3 + l["scoreParts"]["fit"] * 0.2))
    NEAR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data-static", "nearby-cache.json")
    try: near_cache = json.load(open(NEAR))
    except Exception: near_cache = {}
    t0 = time.time()
    for l in leads[: int(os.environ.get("CLOSING_NEARBY", "35"))]:
        if time.time() - t0 > int(os.environ.get("CLOSING_NEARBY_SECS", "420")): break
        if l["place"]:
            k = l["id"]
            if k in near_cache:
                l["nearby"] = near_cache[k]
            else:
                l["nearby"] = nearby(l["place"]["lat"], l["place"]["lon"], l["osmTags"])
                if l["nearby"] is not None: near_cache[k] = l["nearby"]
            if l["nearby"] is not None:
                l["sources"].append({"name": "OpenStreetMap (nearby buyers)", "url": "https://www.openstreetmap.org/#map=11/%s/%s" % (l["place"]["lat"], l["place"]["lon"]), "licence": "ODbL", "trust": "community"})
            time.sleep(1.5)
    ids = {l["id"] for l in leads}
    json.dump({k: v for k, v in near_cache.items() if k in ids}, open(NEAR, "w"))
    # keep cache bounded to the window
    keep = {e["id"].rsplit("/", 1)[-1] for _, e in notices}
    cache = {k: v for k, v in cache.items() if k in keep}
    with open(CACHE, "w") as f:
        json.dump(cache, f)
    status.update({"noticesScanned": len(notices), "noticesFetched": n_fetch, "leads": len(leads), "windowDays": DAYS})
    save("closing.json", {"generatedAt": now_iso(), "status": status, "leads": leads})


if __name__ == "__main__":
    main()
