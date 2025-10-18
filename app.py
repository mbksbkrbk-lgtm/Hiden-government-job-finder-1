from flask import Flask, request, render_template_string
import requests, time, re, os
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, quote_plus

app = Flask(__name__)

# === Configuration ===
# Set your ScraperAPI key in Render environment variable SCRAPERAPI_KEY
SCRAPERAPI_KEY = os.getenv('SCRAPERAPI_KEY', 'YOUR_API_KEY_HERE')
SCRAPERAPI_URL = "http://api.scraperapi.com?api_key={key}&url={url}"

HTML = \"\"\"<!doctype html>
<html>
<head>
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Hidden Gov Vacancy Finder (ScraperAPI)</title>
  <style>
    body{font-family:Arial; background:#f7fafc; padding:18px}
    .card{max-width:1000px;margin:18px auto;background:#fff;padding:18px;border-radius:8px;box-shadow:0 1px 8px rgba(0,0,0,0.06)}
    input[type=text]{width:75%;padding:10px;border:1px solid #ddd;border-radius:6px}
    button{padding:10px 14px;border:none;background:#2563eb;color:#fff;border-radius:6px;cursor:pointer}
    table{width:100%;border-collapse:collapse;margin-top:12px}
    th,td{border:1px solid #eee;padding:8px;text-align:left}
    th{background:#2563eb;color:#fff}
    .meta{color:#666;font-size:13px}
  </style>
</head>
<body>
  <div class=\"card\">
    <h2>Hidden Government Vacancy Finder (ScraperAPI)</h2>
    <p>Enter a Government site URL (for example: https://goidirectory.gov.in). The app uses <b>ScraperAPI</b> to fetch pages so sites that block bots can be reached.</p>
    <p class=\"meta\">Set your ScraperAPI key in Render environment variable <code>SCRAPERAPI_KEY</code>.</p>
    <form method=\"POST\">
      <input type=\"text\" name=\"url\" placeholder=\"Enter full URL e.g. https://goidirectory.gov.in\" required>
      <button type=\"submit\">🔍 Find Hidden Vacancies</button>
    </form>

    {% if error %}
      <p style=\"color:red\">{{ error }}</p>
    {% endif %}

    {% if results is defined %}
      <h3>Scan results for: {{ scanned_site }}</h3>
      <p class=\"meta\">Checked {{ checked_count }} organizations — showing {{ results|length }} vacancy links (skipped common public portals).</p>

      <table>
        <tr><th>#</th><th>Organization</th><th>Career / Vacancy Link</th><th>Snippet</th></tr>
        {% for r in results %}
          <tr>
            <td>{{ loop.index }}</td>
            <td>{{ r.org_name }}</td>
            <td><a href=\"{{ r.career_link }}\" target=\"_blank\">{{ r.career_link }}</a></td>
            <td>{{ r.snippet[:150] }}</td>
          </tr>
        {% endfor %}
      </table>
    {% endif %}
  </div>
</body>
</html>\"\"\"

# Config
USER_AGENT = \"Mozilla/5.0 (compatible; HiddenGovVacFinder/1.0)\"
REQUEST_TIMEOUT = 20
REQUEST_SLEEP = 0.4
MAX_ORGS = 120
PER_ORG_SUBLINKS = 10
KEYWORDS = [\"career\",\"careers\",\"recruit\",\"recruitment\",\"vacancy\",\"vacancies\",\"job\",\"jobs\",\"notification\",\"advertisement\",\"apply\",\"opportunity\"]

SKIP_HOSTS = [
    \"upsc.gov.in\",\"ssc.nic.in\",\"indianrailways.gov.in\",\"railwayrecruitment.gov.in\",
    \"rbi.org.in\",\"nta.ac.in\",\"mhrd.gov.in\",\"employmentnews.gov.in\",\"ncs.gov.in\",
    \"govtjobsportal.in\",\"joinindiancoastguard.gov.in\",\"psu.gov.in\"
]

session = requests.Session()
session.headers.update({\"User-Agent\": USER_AGENT})

def scraperapi_get(target_url):
    if not SCRAPERAPI_KEY or SCRAPERAPI_KEY == \"YOUR_API_KEY_HERE\":
        return None
    url = SCRAPERAPI_URL.format(key=SCRAPERAPI_KEY, url=quote_plus(target_url))
    try:
        r = session.get(url, timeout=REQUEST_TIMEOUT)
        time.sleep(REQUEST_SLEEP)
        if r.status_code == 200:
            return r.text
    except Exception:
        return None
    return None

def normalize_link(base, href):
    try:
        return urljoin(base, href)
    except:
        return href

def is_skippable(url):
    host = urlparse(url).netloc.lower()
    for s in SKIP_HOSTS:
        if s in host:
            return True
    return False

def find_candidate_links(base_url, soup):
    anchors = soup.find_all(\"a\", href=True)
    found = []
    seen = set()
    for a in anchors:
        href = a['href'].strip()
        full = normalize_link(base_url, href)
        low = (href + \" \" + (a.get_text() or \"\")).lower()
        if any(k in low for k in KEYWORDS):
            if full not in seen:
                seen.add(full)
                found.append((a.get_text(strip=True) or full, full))
    return found

def extract_snippet(page_text):
    t = re.sub(r\"\\s+\", \" \", page_text or \"\").strip()
    return t[:300]

@app.route(\"/\", methods=[\"GET\",\"POST\"])
def home():
    if request.method == \"POST\":
        url = request.form.get(\"url\",\"\" ).strip()
        if not url:
            return render_template_string(HTML, error=\"Please enter a valid URL\")
        if not urlparse(url).scheme:
            url = \"https://\" + url
        # fetch root via ScraperAPI
        root_html = scraperapi_get(url)
        if not root_html:
            return render_template_string(HTML, error=\"Cannot open the site (ScraperAPI failed or key not set). Set SCRAPERAPI_KEY in Render.\", scanned_site=None)
        root = url
        soup = BeautifulSoup(root_html, \"html.parser\")
        anchors = soup.find_all(\"a\", href=True)
        orgs = []
        seen_hosts = set()
        for a in anchors:
            href = a['href'].strip()
            if not href:
                continue
            full = normalize_link(root, href)
            parsed = urlparse(full)
            if parsed.scheme not in (\"http\",\"https\"):
                continue
            host = parsed.netloc.lower()
            if host == \"\" or host.startswith(\"mailto:\"):
                continue
            if host in seen_hosts or is_skippable(full):
                continue
            seen_hosts.add(host)
            orgs.append((a.get_text(strip=True) or host, full))
            if len(orgs) >= MAX_ORGS:
                break

        results = []
        checked = 0
        for name, link in orgs:
            checked += 1
            try:
                page_html = scraperapi_get(link)
                if not page_html:
                    continue
                soup2 = BeautifulSoup(page_html, \"html.parser\")
                candidates = find_candidate_links(link, soup2)
                if not candidates:
                    internal = []
                    for a2 in soup2.find_all(\"a\", href=True)[:PER_ORG_SUBLINKS*5]:
                        full2 = normalize_link(link, a2['href'])
                        if urlparse(full2).netloc == urlparse(link).netloc:
                            internal.append(full2)
                    seen_i = set(); internal = [x for x in internal if x not in seen_i and not seen_i.add(x)][:PER_ORG_SUBLINKS]
                    for sub in internal:
                        sub_html = scraperapi_get(sub)
                        if not sub_html:
                            continue
                        if any(k in sub_html.lower() for k in KEYWORDS):
                            ssub = BeautifulSoup(sub_html, \"html.parser\")
                            new = find_candidate_links(sub, ssub)
                            for t,u in new:
                                candidates.append((t,u))
                            snippet = extract_snippet(sub_html)
                            results.append({\"org_name\": name, \"org_url\": link, \"career_link\": sub, \"snippet\": snippet})
                else:
                    for t,u in candidates:
                        snippet = \"\"
                        try:
                            page = scraperapi_get(u)
                            if page:
                                snippet = extract_snippet(page)
                        except:
                            snippet = \"\"
                        results.append({\"org_name\": name, \"org_url\": link, \"career_link\": u, \"snippet\": snippet})
                if len(results) >= 300:
                    break
            except Exception:
                continue

        return render_template_string(HTML, results=results, scanned_site=root, checked_count=checked)
    return render_template_string(HTML)

if __name__ == \"__main__\":
    app.run(host=\"0.0.0.0\", port=10000)
