"""Merge the four tabs into docs/data/desk.json: scores, 'why it's worth your time', first move,
outreach draft, content angle, trust/freshness, and today's five. No network access."""
import json, os, re, datetime, hashlib
from common import load, save, now_iso, days_ago, TODAY

W = {"revival": (0.45, 0.2, 0.35), "import": (0.5, 0.25, 0.25), "closing": (0.45, 0.35, 0.2), "twins": (0.35, 0.3, 0.35)}
TAB_NAMES = {"revival": "Revival broker", "import": "Import scout", "closing": "Treasure hunter", "twins": "Twin finder"}
TRUST_RANK = {"official": 3, "academic": 3, "platform": 2, "community": 2, "official-stale": 1}
audit = load("audit.json", {}) or {}
dead = set(audit.get("deadLinks", []))
flagged = set(audit.get("flagged", []))


def first_move(l):
    t = l["tab"]
    if t == "closing":
        ip = (l.get("ips") or [{}])[0]
        who = ip.get("name")
        how = []
        if ip.get("email"): how.append(f"email {ip['email']}")
        if ip.get("telephone"): how.append(f"call {ip['telephone']}")
        if who:
            return f"Contact the office-holder named in the notice, {who.title()}{' of ' + l['firm'] if l.get('firm') else ''} ({' or '.join(how) or 'details in the notice'}). Ask whether the {l['assets'].split(',')[0]} are being sold, by whom (agent or auction) and when."
        return "Open the Gazette notice for the office-holder's published contact, then ask whether the assets are being sold, by whom and when."
    if t == "import":
        return f"Find the brand's partnerships or franchise contact on its official site{(' (' + l['site'] + ')') if l.get('site') else ''} and ask whether they have UK plans or a UK partner."
    if t == "twins":
        a, b = l["sides"]
        return f"Read both projects properly, then message each maker through their public project page ({a['source']}: issues/discussions or the contact on their site). Ask each separately whether they'd like an intro; only connect them if both say yes."
    k = l.get("kind")
    if k == "Dormant trade mark":
        return "Search the live UK register and Companies House for the last owner (or its successor). If it still exists, write to its company secretary or trade mark attorney asking whether the name is available for assignment or licence."
    if k == "Dormant house":
        return "Read the Wikipedia history and look for who holds the archive (museum, family, owners' club). Run a UK and EU trade mark search on the name before talking to any buyer."
    if k == "Stopped clinical trial":
        return "Contact the sponsor's business-development or licensing team (listed on its corporate site) and ask whether the asset is available for out-licensing."
    return "Open an issue or discussion on the repository (or use the maintainer's public contact) asking whether they'd bless a handover, then line up the most active fork or a company that depends on it."


def outreach(l):
    t = l["tab"]; title = l["title"]
    if t == "closing":
        ip = (l.get("ips") or [{}])[0]
        nm = (ip.get("name") or "").title() or "[office-holder]"
        return (f"Subject: {l['company']['name']}: interest in assets\n\nDear {nm},\n\nI saw the notice in The Gazette about {l['company']['name']}. "
                f"I work with buyers in {l['category'].lower()} and may be able to introduce a serious buyer for the {l['assets'].split(',')[0]} and related assets. "
                "Could you tell me whether the assets are being sold, through which agent or auction house, and the timetable?\n\n"
                "Thank you,\n[Your name]\n[Phone] · [Website]")
    if t == "import":
        return (f"Subject: {title} in the UK\n\nHello,\n\nI'm a London-based connector working with UK retail landlords, operators and department stores. "
                f"{title} has no UK presence that I can find, and I think there's a strong audience for it here. Are you open to a UK partner, franchise or concession? "
                "If so, I'd be glad to arrange introductions on an agreed commission basis.\n\nBest regards,\n[Your name]\n[Phone] · [Website]")
    if t == "twins":
        a, b = l["sides"]
        return (f"Hi {a['by'] or 'there'},\n\nI came across {a['title']} and really liked it. I've also found {b['by'] or 'someone'} in {(b.get('place') or {}).get('countryName') or 'another country'} "
                f"building something very close ({b['title']}). Would you like me to introduce you? No pressure, and I'll only connect you if you both say yes.\n\n[Your name]")
    k = l.get("kind")
    if k in ("Dormant trade mark", "Dormant house"):
        return (f"Subject: The {title} name\n\nDear Sir or Madam,\n\nI'm researching heritage names that are no longer in use, and records suggest {title} may be dormant. "
                "I represent parties interested in sensitively reviving it. Would the rights holder consider an assignment or licence of any remaining rights and archive material? "
                "I'd be grateful to know who the right person to speak to is.\n\nYours faithfully,\n[Your name]\n[Phone] · [Website]")
    if k == "Stopped clinical trial":
        return (f"Subject: Out-licensing enquiry: {l.get('intervention', title)}\n\nDear Business Development team,\n\nThe trial record on ClinicalTrials.gov notes it stopped for this reason: “{l['stalled']}”. "
                "If the programme is available for partnering or out-licensing, I may be able to introduce interested companies. Could you point me to the right contact?\n\nKind regards,\n[Your name]")
    return (f"Hi,\n\nI noticed {title} was {('archived' if 'archived' in l['subtitle'] else 'looking for maintainers')}, and it still has a lot of users. "
            "Would you be open to handing it over to a funded maintainer or company, with your blessing and credit? I'm happy to find and vet candidates.\n\n[Your name]")


def angle(l):
    t = l["tab"]
    if t == "closing": return f"“What happens to a {l['category'].split(' &')[0].split(',')[0].lower()} when it closes?” Follow the kit from the Gazette notice to its next owner."
    if t == "import": return f"“Why can't you buy {l['title']} in Britain?” Show the numbers abroad, the empty map of the UK, and the pitch."
    if t == "twins": return f"“Two strangers, {l['subtitle'].split('·')[-1].strip()}, building the same thing.” Split-screen the two projects, then the intro call (with consent)."
    if l.get("kind") in ("Dormant trade mark", "Dormant house"): return f"“Sleeping beauty: {l['title']}.” Dig through the archive and the register, and ask whether the name can come back."
    if l.get("kind") == "Stopped clinical trial": return "“This treatment didn't fail. It ran out of money.” The quoted reason, and who could pick it up."
    return f"“{l['title']}: loved by thousands, abandoned by its maker.” Who uses it, and can you save it?"


def worth(l):
    t = l["tab"]
    if t == "closing":
        return f"{l['appealLabel'].capitalize()}-appeal assets ({l['assets'].split(',')[0]}) that may be sold off fast; the notice is {max(days_ago(l['date']),0)} days old."
    if t == "import":
        return f"{l['facts'][2][1]} locations abroad and none mapped in the UK: a real gap in {l['category'].lower()}."
    if t == "twins":
        return f"Two small teams in different countries on the same rare thing, with no sign they know each other."
    k = l.get("kind")
    if k == "Dormant trade mark": return f"A name first registered in {l['facts'][3][1][:4]} that lapsed; heritage you can't manufacture."
    if k == "Dormant house": return f"A dissolved house with a Wikipedia history and no recorded successor."
    if k == "Stopped clinical trial": return "Stopped for money, not safety: the science may still be worth finishing."
    return f"{l['facts'][1][1]} stars of proven demand, and the maker has walked away."


def trust(l):
    srcs = l.get("sources", [])
    best = max((TRUST_RANK.get(s.get("trust"), 1) for s in srcs), default=1)
    bad = [s["url"] for s in srcs if s.get("url") in dead]
    label = {3: "Official / scholarly", 2: "Platform / community", 1: "Stale or derived"}[best]
    if bad:
        label += " · link check failed"; best = max(1, best - 1)
    if l["id"] in flagged:
        label += " · didn't match its source today"; best = 1
    return {"level": best, "label": label, "deadLinks": bad}


def freshness(l, gen):
    d = l.get("date")
    if l["tab"] == "revival" and l.get("kind") == "Dormant trade mark":
        return {"level": 1, "label": "Status as of Feb 2018: check the live register"}
    if l["tab"] == "import":
        return {"level": 3, "label": f"UK gap checked {gen[:10]}"}
    if not d: return {"level": 2, "label": "Undated"}
    a = days_ago(d)
    lvl = 3 if a <= 14 else 2 if a <= 120 else 1
    return {"level": lvl, "label": f"{l.get('dateLabel') or 'dated'} {d[:10]}"}


def main():
    tabs = {}
    leads = []
    for t in ("revival", "import", "closing", "twins"):
        d = load(f"{t}.json", {}) or {}
        tabs[t] = {"name": TAB_NAMES[t], "generatedAt": d.get("generatedAt"), "status": d.get("status"), "count": len(d.get("leads", []))}
        for l in d.get("leads", []):
            w = W[t]; sp = l["scoreParts"]
            s = w[0] * sp["value"] + w[1] * sp["fresh"] + w[2] * sp["fit"]
            if l.get("luxury"): s += 0.06
            if any(x.get("trust") == "official-stale" for x in l.get("sources", [])): s -= 0.12
            if t == "revival" and l.get("kind") in ("Stopped clinical trial",): s -= 0.05
            if t == "revival" and l.get("kind") == "Abandoned project" and not l.get("craft"): s -= 0.05
            l["trust"] = trust(l)
            if l["trust"]["deadLinks"]: s -= 0.1
            if l["id"] in flagged: s -= 0.25
            l["freshness"] = freshness(l, d.get("generatedAt") or now_iso())
            l["score"] = round(max(0, min(1, s)) * 100)
            l["worth"] = worth(l); l["firstMove"] = first_move(l); l["outreach"] = outreach(l); l["angle"] = angle(l)
            l["tabName"] = TAB_NAMES[t]
            leads.append(l)
    leads.sort(key=lambda l: -l["score"])
    BYID = {l["id"]: l for l in leads}
    # today's five: best of each tab, then the next best overall; rotate ties by date so it changes daily
    seed = TODAY.isoformat()
    five, seen = [], set()
    for t in ("closing", "revival", "import", "twins"):
        pool = [l for l in leads if l["tab"] == t][:6]
        if pool:
            pick = sorted(pool, key=lambda l: hashlib.md5((seed + l["id"]).encode()).hexdigest())[0] if t != "closing" else pool[0]
            five.append(pick["id"]); seen.add(pick["id"])
    kinds = {BYID[i].get("kind") for i in five}
    for l in leads:
        if len(five) >= 5: break
        if l["id"] not in seen and l.get("kind") not in kinds: five.append(l["id"]); seen.add(l["id"])
    save("desk.json", {"generatedAt": now_iso(), "tabs": tabs, "today": five, "audit": {k: audit.get(k) for k in ("generatedAt", "summary", "spotChecks", "linkCheck", "schema")}, "leads": leads})


if __name__ == "__main__":
    main()
