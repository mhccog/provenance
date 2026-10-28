"""Shared helpers: polite HTTP with retries, JSON IO, small text utils. Stdlib only."""
import json, os, time, urllib.request, urllib.parse, urllib.error, re, math, datetime

UA = "Provenance-lead-desk/1.0 (+https://github.com/mhccog/provenance; open-data research)"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "docs", "data")
STATIC = os.path.join(ROOT, "data-static")
TODAY = datetime.date.today()


def get(url, params=None, headers=None, tries=4, timeout=60, raw=False, data=None):
    if params:
        url = url + ("&" if "?" in url else "?") + urllib.parse.urlencode(params, doseq=True)
    h = {"User-Agent": UA, "Accept": "application/json"}
    if headers:
        h.update(headers)
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=h, data=data)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                b = r.read()
                return b if raw else json.loads(b.decode("utf-8"))
        except urllib.error.HTTPError as e:
            last = e
            if e.code == 403 and "api.github.com" in url and i < tries - 1:
                reset = e.headers.get("x-ratelimit-reset"); rem = e.headers.get("x-ratelimit-remaining")
                wait = 65
                if rem == "0" and reset:
                    wait = max(5, min(900, int(reset) - int(time.time()) + 3))
                print(f"github rate limit; waiting {wait}s")
                time.sleep(wait)
                continue
            if e.code in (400, 401, 403, 404, 410, 422):
                raise
            time.sleep(2 * (i + 1) + (20 if e.code == 429 else 0))
        except Exception as e:  # network blips
            last = e
            time.sleep(2 * (i + 1))
    raise last


def gh_headers():
    t = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    h = {"Accept": "application/vnd.github+json"}
    if t:
        h["Authorization"] = "Bearer " + t
    return h


def save(name, obj):
    p = os.path.join(DATA, name)
    with open(p, "w") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
    print("wrote", p, os.path.getsize(p), "bytes")


def load(name, default=None, static=False):
    p = os.path.join(STATIC if static else DATA, name)
    try:
        with open(p) as f:
            return json.load(f)
    except Exception:
        return default


def days_ago(d):
    try:
        return (TODAY - datetime.date.fromisoformat(str(d)[:10])).days
    except Exception:
        return 9999


def fresh(d, half_life=30):
    """1.0 today, 0.5 after half_life days."""
    return 0.5 ** (max(days_ago(d), 0) / half_life)


def clean(s, n=None):
    s = re.sub(r"<[^>]+>", " ", s or "")
    s = re.sub(r"\s+", " ", s).strip()
    if n and len(s) > n:
        s = s[: n - 1].rsplit(" ", 1)[0] + "…"
    return s


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


OVERPASS = ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter", "https://overpass.private.coffee/api/interpreter"]


def overpass(q, timeout=240):
    """POST an Overpass QL query, falling back across public instances."""
    last = None
    for ep in OVERPASS:
        try:
            return get(ep, data=("data=" + urllib.parse.quote(q)).encode(), timeout=timeout, tries=2)
        except Exception as e:
            print("overpass", ep, e); last = e
            time.sleep(5)
    raise last
