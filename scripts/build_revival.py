"""Revival broker: sleeping beauties (dormant heritage marks and houses) plus abandoned projects.
Sources: UK IPO open data snapshot (OGL v3), Wikidata (CC0), Wikipedia links, GitHub REST API (public metadata),
ClinicalTrials.gov API v2 (US NLM, public domain)."""
import os, re, json, time, datetime, base64, urllib.parse
from common import get, save, load, clean, fresh, days_ago, now_iso, gh_headers, TODAY, STATIC

LUXW = {"watches & jewellery": 1.0, "perfume & cosmetics": .9, "wines & spirits": .95, "motoring & coachbuilding": .95,
        "leather goods": .85, "tailoring & fashion": .8, "hotels & dining": .8, "porcelain & glass": .75, "fine textiles": .7, "cutlery & blades": .7}
status = {}


def ipo_link(num):
    return f"https://trademarks.ipo.gov.uk/ipo-tmcase/page/Results/1/{num}"


def marks():
    d = load("sleeping-marks.json", static=True) or {"marks": []}
    out = []
    for m in d["marks"][:int(os.environ.get("MARKS_MAX", "200"))]:
        age = 2018 - int(m["filed"][:4])
        cls = m["classLabels"]
        val = max(LUXW.get(c, .6) for c in cls)
        title = m["mark"].strip().rstrip(",.")
        out.append({
            "id": "tm-" + m["tmNum"], "tab": "revival", "kind": "Dormant trade mark", "title": title,
            "subtitle": f"{' · '.join(cls[:3])} · first filed {m['filed'][:4]}",
            "date": m["expired"], "dateLabel": "registration lapsed",
            "facts": [["Mark", title], ["Last owner on record", m["owner"]], ["Owner region", ", ".join(filter(None, [m.get("region"), m.get("country")]))],
                      ["First filed", m["filed"]], ["Status (Feb 2018)", m["status"]], ["Lapsed / renewal date", m["expired"]],
                      ["Mark type", m["type"]], ["Classes", ", ".join(str(c) for c in m["lux"])]],
            "stalled": f"Registration recorded as {m['status'].lower()} (renewal date {m['expired']}) in the IPO's Feb 2018 open-data snapshot, after about {age} years on the register.",
            "category": cls[0], "luxury": True,
            "warning": "Check before use: a lapsed registration can still carry goodwill and passing-off rights, and someone may have re-filed since 2018. Search the live register and take advice before any assignment or filing.",
            "who": [f"Heritage-revival investors and family offices in {cls[0]}", "Brand-revival specialists and IP brokers", f"The last recorded owner, {m['owner']}, if it still trades (they can assign any residual goodwill)"],
            "deal": "Broker an assignment or consent from the last owner (or its successor) to a buyer who will relaunch the name; finder's fee from the buyer, or a small equity stake in the relaunch.",
            "sources": [{"name": "UK IPO register (live record)", "url": ipo_link(m["tmNum"]), "licence": "OGL v3", "trust": "official"},
                        {"name": "IPO open data snapshot (Feb 2018)", "url": d.get("url"), "licence": "OGL v3", "trust": "official-stale"}],
            "scoreParts": {"value": round(val * min(1, m["score"]), 3), "fresh": round(min(age, 140) / 140, 3), "fit": 0.6 if m["type"] == "Word" else 0.45},
            "freshnessNote": "Snapshot Feb 2018 (IPO has published no newer bulk file)",
        })
    status["marks"] = {"ok": True, "n": len(out), "note": "IPO snapshot Feb 2018 (static)"}
    return out


WD_LUX = re.compile(r"watch|jewel|perfum|fragrance|luxury|haute|leather|tailor|porcelain|silversmith|goldsmith|coachbuil|fashion|whisk|distill|cognac|champagne|hotel|yacht", re.I)


def wikidata_houses():
    q = open(os.path.join(os.path.dirname(__file__), "wikidata_dormant.rq")).read()
    rows = None
    for i in range(3):
        try:
            rows = get("https://query.wikidata.org/sparql", {"query": q}, headers={"Accept": "application/sparql-results+json"}, timeout=90, tries=1)["results"]["bindings"]
            json.dump(rows, open(os.path.join(STATIC, "wikidata-dormant-cache.json"), "w"))
            status["wikidata"] = {"ok": True, "n": len(rows)}
            break
        except Exception as e:
            print("wikidata retry", e); time.sleep(15)
    if rows is None:
        rows = load("wikidata-dormant-cache.json", [], static=True)
        status["wikidata"] = {"ok": False, "n": len(rows), "note": "query service timed out; using last good copy"}
    tmlive = load("tm-live-2018.json", {}, static=True)
    by = {}
    for b in rows:
        qid = b["x"]["value"].rsplit("/", 1)[-1]
        lab = b.get("xLabel", {}).get("value", "")
        if re.fullmatch(r"Q\d+", lab): continue
        r = by.setdefault(qid, {"qid": qid, "label": lab, "desc": b.get("xDescription", {}).get("value", ""), "ind": set(), "country": set(),
                                "inc": None, "dis": None, "wiki": b.get("article", {}).get("value")})
        r["ind"].add(b.get("indLabel", {}).get("value", ""))
        if b.get("countryLabel"): r["country"].add(b["countryLabel"]["value"])
        if b.get("inc"): r["inc"] = min(filter(None, [r["inc"], b["inc"]["value"][:10]]))
        if b.get("dis"): r["dis"] = max(filter(None, [r["dis"], b["dis"]["value"][:10]]))
    cands = []
    for r in by.values():
        if not r["wiki"]: continue
        if re.search(r"retail|discount|supermarket|holding|chain of|plc|bank|insurance|dealer", r["desc"] + " " + r["label"], re.I): continue
        ind = " ".join(r["ind"])
        lux = bool(WD_LUX.search(ind + " " + r["desc"]))
        uk = bool(r["country"] & {"United Kingdom", "England", "Scotland", "Wales", "United Kingdom of Great Britain and Ireland"})
        try: inc = int(r["inc"][:4].lstrip("+-") or 0) if r["inc"] else None
        except: inc = None
        v = (0.55 if lux else 0.35) + (0.25 if uk else 0) + (0.15 if inc and inc < 1950 else 0)
        if tmlive.get(r["label"]) is False: v += 0.05
        r["v"] = v; r["lux"] = lux; r["uk"] = uk; r["incY"] = inc
        cands.append(r)
    cands.sort(key=lambda r: -r["v"])
    cands = cands[:120]
    # check succession / current ownership claims; drop houses that were simply merged into a living owner
    ents = {}
    for i in range(0, len(cands), 50):
        ids = "|".join(r["qid"] for r in cands[i:i + 50])
        try:
            ents.update(get("https://www.wikidata.org/w/api.php", {"action": "wbgetentities", "ids": ids, "props": "claims|sitelinks", "format": "json"})["entities"])
        except Exception as e:
            print("wbgetentities", e)
    out = []
    for r in cands:
        e = ents.get(r["qid"], {})
        cl = e.get("claims", {})
        succ = any(p in cl for p in ("P1366", "P127", "P749"))  # replaced by / owned by / parent
        nsite = len(e.get("sitelinks", {}))
        if succ: continue
        coord = None
        try:
            c = cl["P625"][0]["mainsnak"]["datavalue"]["value"]; coord = {"lat": c["latitude"], "lon": c["longitude"], "label": "Wikidata coordinates", "precision": "wikidata"}
        except Exception:
            pass
        tm = tmlive.get(r["label"])
        tmtxt = "No live UK mark containing the name in the IPO Feb 2018 snapshot" if tm is False else ("A live UK mark containing the name existed in 2018" if tm else "Not checked against the UK mark snapshot")
        ctry = ", ".join(sorted(r["country"])) or "country not stated"
        out.append({
            "id": "wd-" + r["qid"], "tab": "revival", "kind": "Dormant house", "title": r["label"],
            "subtitle": f"{', '.join(sorted(i for i in r['ind'] if i))[:80]} · {ctry}",
            "date": r["dis"], "dateLabel": "dissolved",
            "facts": [["Founded", (r["inc"] or "?")[:4].lstrip("+")], ["Dissolved", (r["dis"] or "?")[:4].lstrip("+")], ["Country", ctry],
                      ["Wikipedia language editions", str(nsite)], ["UK mark check", tmtxt]],
            "stalled": f"Wikidata records it as dissolved in {(r['dis'] or '?')[:4].lstrip('+')}, with no successor or owner recorded. " + clean(r["desc"]),
            "category": "Heritage marque" if not r["lux"] else "Heritage luxury house", "luxury": r["lux"], "place": coord,
            "warning": "Check before use: no successor on Wikidata doesn't mean the name is free. Goodwill, overseas marks or a family estate may still hold rights.",
            "who": ["Heritage-revival investors and collectors' clubs for the marque", "Craft makers who could produce under licence (coachbuilders, watchmakers, perfumers…)", "Descendants or estate holding archives, if publicly known"],
            "deal": "Broker an archive and name deal between rights holders (if any) and a revival team; finder's fee or equity in the relaunch.",
            "sources": [{"name": "Wikidata", "url": f"https://www.wikidata.org/wiki/{r['qid']}", "licence": "CC0", "trust": "community"},
                        {"name": "Wikipedia", "url": r["wiki"], "licence": "CC BY-SA (linked, not copied)", "trust": "community"}],
            "scoreParts": {"value": round(min(r["v"], 1), 3), "fresh": round(min(nsite, 20) / 20, 3), "fit": 0.9 if tm is False else 0.6},
        })
    status["houses"] = {"ok": True, "n": len(out)}
    return out[:70]


CRAFT_TOPICS = ["design", "typography", "font", "synthesizer", "audio", "camera", "photography", "3d-printing", "fashion",
                "generative-art", "keyboard", "watch", "hardware", "music", "art", "embroidery", "knitting", "woodworking"]


def readme_reason(full):
    try:
        d = get(f"https://api.github.com/repos/{full}/readme", headers=gh_headers(), tries=2)
        txt = base64.b64decode(d["content"]).decode("utf-8", "ignore")
    except Exception:
        return None
    if re.search(r"(has )?moved to|new home|now lives|migrated to|moved over to|continued (at|in)|successor|replaced by|superseded|development continues|now maintained (at|in)|see the new|in favou?r of|merged into", txt, re.I):
        return "MOVED"
    txt = re.sub(r"<[^>]+>|!\[[^\]]*\]\([^)]*\)|\[([^\]]*)\]\([^)]*\)", r"\1", txt)
    for line in re.split(r"(?<=[.!?])\s+|\n", txt):
        if re.search(r"no longer (being )?maintained|unmaintained|archived|deprecated|looking for (a )?(new )?maintainer|abandoned|not actively|discontinued|end of life|sunset", line, re.I):
            s = clean(line.strip("#>*-_ `"), 220)
            if len(s) > 15: return s
    return None


def github():
    since = (TODAY - datetime.timedelta(days=540)).isoformat()
    qs = [(f"archived:true stars:>1500 pushed:>{since}", 40, 0)]
    for t in CRAFT_TOPICS:
        qs.append((f"archived:true stars:>150 topic:{t} pushed:>{(TODAY - datetime.timedelta(days=900)).isoformat()}", 8, 1))
    qs.append((f'"looking for a maintainer" in:readme stars:>300 archived:false', 15, 0))
    qs.append((f'"looking for maintainers" in:readme stars:>300 archived:false', 15, 0))
    seen, items = set(), []
    ok = True
    for q, n, craft in qs:
        try:
            d = get("https://api.github.com/search/repositories", {"q": q, "sort": "stars", "order": "desc", "per_page": n}, headers=gh_headers())
        except Exception as e:
            print("gh search", q, e); ok = False; continue
        for it in d.get("items", []):
            if it["full_name"] in seen or it.get("fork"): continue
            seen.add(it["full_name"]); it["_craft"] = craft; items.append(it)
        time.sleep(2.2)
    items.sort(key=lambda it: -(it["stargazers_count"] * (2 if it["_craft"] else 1)))
    out = []
    for it in items[:110]:
        if len(out) >= 60: break
        full = it["full_name"]
        if re.search(r"awesome|best-|list|interview|roadmap|tutorial|course|books|resources|cheatsheet", it["name"], re.I) or not it.get("description"):
            continue
        reason = readme_reason(full)
        if reason == "MOVED":
            continue
        forks = []
        try:
            fs = get(f"https://api.github.com/repos/{full}/forks", {"sort": "stargazers", "per_page": 6}, headers=gh_headers(), tries=2)
            for f in fs:
                if f["stargazers_count"] >= 3 or days_ago(f["pushed_at"]) < 180:
                    forks.append({"name": f["full_name"], "url": f["html_url"], "stars": f["stargazers_count"], "pushed": f["pushed_at"][:10]})
        except Exception:
            pass
        lic = (it.get("license") or {}).get("spdx_id") or "no licence stated"
        craft = it["_craft"] or bool(set(it.get("topics", [])) & set(CRAFT_TOPICS))
        why = reason or ("Archived by its owner on GitHub; no reason stated in the README." if it["archived"] else "README asks for new maintainers.")
        stars = it["stargazers_count"]
        out.append({
            "id": "gh-" + str(it["id"]), "tab": "revival", "kind": "Abandoned project", "title": it["name"],
            "subtitle": f"{full} · ★ {stars:,} · {it.get('language') or 'code'} · {'archived' if it['archived'] else 'seeking maintainers'}",
            "date": it["pushed_at"][:10], "dateLabel": "last push",
            "facts": [["What it is", clean(it.get("description"), 200) or "(no description)"], ["Stars", f"{stars:,}"], ["Forks", f"{it['forks_count']:,}"],
                      ["Open issues", str(it["open_issues_count"])], ["Licence", lic], ["Topics", ", ".join(it.get("topics", [])[:6]) or "-"]],
            "stalled": why, "stalledQuoted": bool(reason), "category": "Design & craft software" if craft else "Software",
            "luxury": False, "craft": craft,
            "continuers": forks,
            "who": ([f"Active fork: {f['name']} (★{f['stars']}, pushed {f['pushed']})" for f in forks[:3]] or ["No active forks found: the field is open"]) +
                   ["Companies whose products depend on it (check the dependents graph)"],
            "deal": ("Broker a handover: the owner transfers the repo/name and the community to a funded maintainer or company; finder's fee or paid sponsorship deal. "
                     + ("Its open licence already lets anyone fork, so what you're selling is the name, the community and the maker's blessing." if lic not in ("no licence stated", "NOASSERTION") else "No open licence: any reuse needs the owner's permission, which makes the blessing essential.")),
            "sources": [{"name": "GitHub", "url": it["html_url"], "licence": f"metadata via GitHub API; code under {lic}", "trust": "platform"}],
            "scoreParts": {"value": round(min(1, (len(str(stars)) - 1) / 5) * (1 if craft else .8), 3), "fresh": round(fresh(it["pushed_at"], 180), 3), "fit": 0.9 if reason else 0.6},
        })
        time.sleep(0.3)
    status["github"] = {"ok": ok, "n": len(out)}
    return out


def trials():
    term = "AREA[WhyStopped](funding OR financial OR business OR commercial OR strategic OR portfolio OR \"lack of funds\" OR \"company decision\")"
    since = (TODAY - datetime.timedelta(days=730)).isoformat()
    try:
        d = get("https://clinicaltrials.gov/api/v2/studies", {"query.term": term + f" AND AREA[LastUpdatePostDate]RANGE[{since},MAX]",
               "filter.overallStatus": "TERMINATED|WITHDRAWN|SUSPENDED", "pageSize": 200, "sort": "LastUpdatePostDate:desc",
               "fields": "NCTId,BriefTitle,WhyStopped,OverallStatus,LeadSponsorName,LeadSponsorClass,Condition,InterventionName,InterventionType,Phase,EnrollmentCount,LastUpdatePostDate,LocationCountry,LocationCity,LocationGeoPoint"})
    except Exception as e:
        status["trials"] = {"ok": False, "error": str(e)}; return []
    out = []
    for s in d.get("studies", []):
        p = s["protocolSection"]
        why = (p["statusModule"].get("whyStopped") or "")
        if re.search(r"safety|efficacy|futility|toxic|adverse|death|ineffective|risk|benefit", why, re.I): continue
        phases = p.get("designModule", {}).get("phases", [])
        if not set(phases) & {"PHASE2", "PHASE3", "PHASE1"}: continue
        enr = (p.get("designModule", {}).get("enrollmentInfo") or {}).get("count") or 0
        iv = [i.get("name") for i in p.get("armsInterventionsModule", {}).get("interventions", []) if i.get("type") in ("DRUG", "DEVICE", "BIOLOGICAL")]
        if not iv: continue
        locs = p.get("contactsLocationsModule", {}).get("locations", [])
        place = None
        for l in locs:
            if l.get("geoPoint"):
                place = {"lat": l["geoPoint"]["lat"], "lon": l["geoPoint"]["lon"], "label": f"{l.get('city')}, {l.get('country')} (a trial site)", "precision": "trial site"}; break
        conds = p.get("conditionsModule", {}).get("conditions", [])
        nct = p["identificationModule"]["nctId"]; sp = p["sponsorCollaboratorsModule"]["leadSponsor"]
        out.append({
            "id": "ct-" + nct, "tab": "revival", "kind": "Stopped clinical trial", "title": p["identificationModule"]["briefTitle"],
            "subtitle": f"{', '.join(iv[:2])} · {', '.join(conds[:2])} · {'/'.join(x.replace('PHASE', 'Phase ') for x in phases)}",
            "date": p["statusModule"]["lastUpdatePostDateStruct"]["date"], "dateLabel": "record updated",
            "facts": [["Sponsor", sp.get("name")], ["Sponsor type", sp.get("class", "").title()], ["Status", p["statusModule"]["overallStatus"].title()],
                      ["Participants enrolled", str(enr)], ["Intervention", ", ".join(iv[:3])], ["Countries", ", ".join(sorted({l.get('country') for l in locs if l.get('country')}))[:120] or "-"]],
            "stalled": why, "stalledQuoted": True, "category": "Life sciences", "luxury": False, "place": place,
            "conditions": conds[:3], "intervention": iv[0],
            "who": [f"Sponsors running active trials in {conds[0] if conds else 'this condition'} (see 'Find who else is working on it')", "Specialist pharma that in-license shelved assets", "Patient foundations for the condition"],
            "deal": "Broker an out-licence of the shelved asset from the sponsor to a company that will finish it; success fee from the licensee (licensing deals often pay brokers a percentage of upfront).",
            "sources": [{"name": "ClinicalTrials.gov", "url": f"https://clinicaltrials.gov/study/{nct}", "licence": "US Government work (public domain)", "trust": "official"}],
            "scoreParts": {"value": round(0.45 + (0.2 if "PHASE3" in phases else 0.1 if "PHASE2" in phases else 0) + (0.1 if sp.get("class") == "INDUSTRY" else 0), 3),
                           "fresh": round(fresh(p["statusModule"]["lastUpdatePostDateStruct"]["date"], 120), 3), "fit": 0.7},
        })
    out.sort(key=lambda l: -(l["scoreParts"]["value"] + l["scoreParts"]["fresh"]))
    out = out[:40]
    # who else is working on it: other sponsors' recruiting trials in the same first condition
    for l in out[:25]:
        if not l.get("conditions"): continue
        try:
            d = get("https://clinicaltrials.gov/api/v2/studies", {"query.cond": l["conditions"][0], "filter.overallStatus": "RECRUITING", "pageSize": 20,
                                                                  "fields": "NCTId,LeadSponsorName,LeadSponsorClass"})
            sps = []
            for s in d.get("studies", []):
                sp = s["protocolSection"]["sponsorCollaboratorsModule"]["leadSponsor"]
                if sp.get("class") == "INDUSTRY" and sp["name"] not in sps and sp["name"] not in l["facts"][0][1]:
                    sps.append(sp["name"])
            if sps:
                l["who"][0] = "Companies recruiting now in the same condition: " + ", ".join(sps[:5])
        except Exception:
            pass
        time.sleep(0.4)
    status["trials"] = {"ok": True, "n": len(out)}
    return out


LUX_SIC = {"32120": "Manufacture of jewellery", "32130": "Imitation jewellery", "26520": "Watches and clocks", "15120": "Luggage, handbags and saddlery",
           "15200": "Footwear", "14190": "Other wearing apparel", "14131": "Men's outerwear", "14132": "Women's outerwear", "11010": "Distilled spirits",
           "11020": "Wine from grape", "20420": "Perfumes and toilet preparations", "29200": "Coachwork for motor vehicles", "30120": "Pleasure and sporting boats",
           "55100": "Hotels", "23410": "Ceramic household and ornamental articles", "25710": "Cutlery", "47770": "Retail of watches and jewellery"}


def companies_house():
    """Dissolved UK companies in luxury SIC codes incorporated before 1960. Needs the free COMPANIES_HOUSE_API_KEY secret."""
    key = os.environ.get("COMPANIES_HOUSE_API_KEY")
    if not key:
        status["companiesHouse"] = {"ok": False, "note": "Not run: add the free COMPANIES_HOUSE_API_KEY secret to enable dissolved heritage companies."}
        return []
    auth = "Basic " + base64.b64encode((key + ":").encode()).decode()
    out = []
    for sic, label in LUX_SIC.items():
        try:
            d = get("https://api.company-information.service.gov.uk/advanced-search/companies",
                    {"company_status": "dissolved", "sic_codes": sic, "incorporated_to": "1960-12-31", "size": 50}, headers={"Authorization": auth})
        except Exception as e:
            print("CH", sic, e); continue
        for c in d.get("items", []):
            inc = c.get("date_of_creation", ""); dis = c.get("date_of_cessation", "")
            age = 2026 - int(inc[:4]) if inc[:4].isdigit() else 0
            out.append({
                "id": "ch-" + c["company_number"], "tab": "revival", "kind": "Dissolved heritage company", "title": c["company_name"].title(),
                "subtitle": f"{label} · incorporated {inc[:4]} · dissolved {dis[:4]}", "date": dis, "dateLabel": "dissolved",
                "facts": [["Company number", c["company_number"]], ["Incorporated", inc], ["Dissolved", dis], ["SIC", f"{sic} {label}"],
                          ["Registered office (last)", ", ".join(filter(None, [(c.get("registered_office_address") or {}).get(k) for k in ("locality", "postal_code")]))]],
                "stalled": f"Dissolved on {dis} after {age} years (Companies House).", "category": label, "luxury": True,
                "warning": "Check before use: the name may be protected by goodwill, a live trade mark or a successor company.",
                "who": ["Heritage-revival investors", f"Makers in {label.lower()} wanting provenance"],
                "deal": "Clear the name (trade mark search), then broker it with archive research to a relaunch team; finder's fee or equity.",
                "sources": [{"name": "Companies House", "url": f"https://find-and-update.company-information.service.gov.uk/company/{c['company_number']}", "licence": "OGL v3", "trust": "official"}],
                "scoreParts": {"value": 0.9, "fresh": round(min(age, 120) / 120, 3), "fit": 0.8},
            })
        time.sleep(0.6)
    status["companiesHouse"] = {"ok": True, "n": len(out)}
    return out


def main():
    leads = []
    for fn in (marks, wikidata_houses, companies_house, github, trials):
        try:
            leads += fn()
        except Exception as e:
            print(fn.__name__, "failed", e); status[fn.__name__] = {"ok": False, "error": str(e)}
    save("revival.json", {"generatedAt": now_iso(), "status": status, "leads": leads})


if __name__ == "__main__":
    main()
