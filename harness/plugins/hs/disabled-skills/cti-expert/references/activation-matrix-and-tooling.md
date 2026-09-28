# Technique Activation Matrix & Tooling

## Technique Activation Matrix

Which techniques activate per target type in a `/case` run:

| Technique | Person | Domain | Org | Username | Email | IP |
|-----------|--------|--------|-----|----------|-------|----|
| `/sweep` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `/query` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `/username` | ✅ | — | ✅* | ✅ | — | — |
| `/email-deep` | ✅ | — | ✅* | — | ✅ | — |
| `/phone` | ✅ | — | ✅* | — | — | — |
| `/breach-deep` (LeakCheck + HudsonRock) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `/subdomain` | — | ✅ | ✅ | — | — | — |
| `/traffic` | — | ✅ | ✅ | — | — | — |
| `/threat-check` | — | ✅ | ✅ | — | — | ✅ |
| `/secrets` | — | ✅ | ✅ | ✅ | — | — |
| `/scam-check` | — | ✅ | ✅ | — | — | — |
| `/branch` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `/gdoc` | — | ✅ | ✅ | — | — | — |
| `/sharelink` | ✅ | — | ✅ | ✅ | ✅ | — |
<!-- dork-integration:phase-05 start -->
| `/dork-sweep` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅* |
| `/docleak` | ✅ | ✅ | ✅ | ✅* | — | — |
<!-- dork-integration:phase-05 end -->
| Social media platforms | ✅ | — | ✅ | ✅ | — | — |
| Metadata forensics | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Photo verification | ✅ | — | ✅* | ✅ | — | — |
| Network analysis | — | ✅ | ✅ | — | — | ✅ |
| Advanced geolocation | ✅ | — | — | ✅ | — | — |
| Web & DNS forensics | — | ✅ | ✅ | — | ✅ | ✅ |
| `/timeline` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `/exposure` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `/threat-model` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `/wifi` (SSID/BSSID) | ✅ | ✅ | ✅ | — | — | ✅ |
| Visitor intelligence | — | ✅ | ✅ | — | — | ✅ |
| Cloud audit | — | ✅ | ✅ | — | — | ✅ |
| MSFTRecon (M365/Azure tenant) | — | ✅ | ✅ | — | — | — |
| Dependency audit | — | ✅ | ✅ | — | — | — |
| Disk forensics | — | — | — | — | — | — |
| Incident triage | — | ✅ | ✅ | — | — | ✅ |
| OWASP audit | — | ✅ | ✅ | — | — | — |
| Prompt injection audit | — | ✅ | ✅ | — | — | — |
| `/snapshots` | — | ✅ | ✅ | — | — | ✅ |
| `/diff` | — | ✅ | ✅ | — | — | ✅ |
| `/drift` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `/render threat-path` | — | ✅ | ✅ | — | — | ✅ |
| `/render attack-surface` | — | ✅ | ✅ | — | — | ✅ |
| `/blind-spots` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `/source-check` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `/report ioc` | — | ✅ | ✅ | — | — | ✅ |
| `/report` + `/brief` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Shodan InternetDB (ports/tags/vulns) | — | ✅ | ✅ | — | — | ✅ |
| GreyNoise Community (noise/threat class) | — | ✅ | ✅ | — | — | ✅ |
| URLScan.io passive (scan history) | — | ✅ | ✅ | — | — | — |
| Disposable email check (kickbox) | ✅ | — | ✅* | — | ✅ | — |
| URLhaus (malware URL hosting) | — | ✅ | ✅ | — | — | ✅ |
| ThreatFox (IOC/C2 lookup) | — | ✅ | ✅ | — | — | ✅ |
| MalwareBazaar (hash → malware family) | — | — | — | — | — | — |
| ipwho.is (geo + ASN + ISP) | — | ✅ | ✅ | — | — | ✅ |
| DMARC/SPF/DKIM check (DNS) | — | ✅ | ✅ | — | ✅ | — |

`✅*` — runs for discovered key personnel within the organization
`MalwareBazaar` — activates only via `/hash [value]` when a file hash is discovered during investigation

**Adaptive chaining:** Each phase auto-feeds newly discovered identifiers into subsequent phases. E.g. `/sweep` on a domain finding an email auto-triggers `/email-deep` + `/breach-deep`.

<!-- dork-integration:phase-05 start -->
**`✅*` dork coverage notes:** `/dork-sweep` on IP runs against reverse-DNS hostname once resolved (graceful skip if no rDNS); `/docleak` on Username targets document-author/uploader fields on scribd, slideshare, academia.edu, researchgate.

**Dork auto-fire matrix — every `/case` target type gains coverage:**
- Person → `/dork-sweep --telegram --docs` + `/docleak` on full name
- Domain → `/dork-sweep --filetype --docs` + `/docleak` on domain + org name
- Org → `/dork-sweep --filetype --docs --telegram` + `/docleak` on org + primary domain
- Username → `/dork-sweep --telegram --docs` + `/docleak` (author-angle)
- Email → `/dork-sweep --telegram --docs` on email + `@domain`
- IP → `/dork-sweep` on rDNS-resolved hostname (skipped if no rDNS)

Adaptive fan-out: discovered emails → Telegram dork; discovered personnel → `/docleak`; discovered subdomains → filetype dork; discovered usernames → Telegram + doc sweep; discovered IPs → rDNS → dork-sweep.
<!-- dork-integration:phase-05 end -->

On Domain/Org target, `/case`/`/sweep` inspect MX + SPF TXT. If MX ends `protection.outlook.com` OR SPF contains `spf.protection.outlook.com` → `/msftrecon` auto-fires in Acquire. Results feed subject registry as `infrastructure` findings (tenant ID, federation type, MDI presence) + `/exposure` scoring.

**`/case` pipeline walkthrough (M365-hosted Domain/Org):** (a) standard DNS/WHOIS/subdomain/traffic/scam-check/breach-deep checks run first, (b) M365 indicators present → `/msftrecon` auto-fires, no extra flag, (c) discovered tenant ID pivots `/branch` in Enrich (search other domains, same tenant). No user intervention required.

**Parallel enrichment (3+ subjects):** Acquire discovering 3+ subjects → enrichment fans out in parallel via AgentFlow DAG orchestration; each subject's enrichment runs independently, merges with dedup before Assess. Disable: `--sequential`. See `techniques/agentflow-enrichment.md`.

---

## Exposure Score Bands

| Range | Label | Action |
|-------|-------|--------|
| 0–25 | Minimal | Passive monitoring sufficient |
| 26–50 | Moderate | Periodic review advised |
| 51–75 | Elevated | Address within 30 days |
| 76–100 | Critical | Immediate escalation required |

---

## Tool Priority & Fallback

1. Check `agent-browser` availability first; use `hs:chrome-profile` only if real user Chrome cookies are required
2. Use `agent-browser` for generic screenshot evidence and interactive UI; use `hs:chrome-profile` only when real Chrome profile state is required
3. Use Scrapling DynamicFetcher for: JS-heavy sites, SPA content, auto-escalation from static
4. Use Scrapling StealthyFetcher for: anti-bot bypass, Cloudflare-protected targets
5. Use Scrapling Fetcher for: fast static page collection, HTML parsing (~2ms)
6. Fall back to web search → web fetch → direct curl — no investigation blockers
7. Tag each finding with collection method: `[browser]` · `[scrapling-dynamic]` · `[scrapling-stealth]` · `[scrapling-static]` · `[search]` · `[fetch]` · `[manual]` · `[whois-lib]` · `[whois-cli]` · `[whois-api]`

---

## Tool Auto-Install Policy

**Before running any CLI tool, check if it exists on the system. If not, install it automatically and silently.** This ensures zero-friction investigation — the analyst never stalls on missing dependencies.

### Auto-Install Protocol

1. **Check:** `command -v <tool> >/dev/null 2>&1` (or `python -m <module> --help` for Python modules)
2. **Install:** If missing, run the install command from the table below
3. **Verify:** Confirm installation succeeded before proceeding
4. **Log:** Note `[auto-installed]` in the finding's collection method tag
5. **Continue:** Proceed with the investigation — never block on tool availability

### Install Commands by Tool

| Tool | Check Command | Install Command |
|------|--------------|-----------------|
| Maigret | `command -v maigret` | `pip3 install maigret` |
| Sherlock | `command -v sherlock` | `pipx install sherlock-project` |
| Blackbird | `command -v blackbird` | `pip3 install blackbird-osint` |
| PhoneInfoga | `command -v phoneinfoga` | `go install github.com/sundowndev/phoneinfoga/v2/cmd/phoneinfoga@latest` |
| Holehe | `command -v holehe` | `pip3 install holehe` |
| h8mail | `command -v h8mail` | `pip3 install h8mail` |
| theHarvester | `command -v theHarvester` | `pip3 install theHarvester` |
| TruffleHog | `command -v trufflehog` | `pip3 install trufflehog` |
| Gitleaks | `command -v gitleaks` | `go install github.com/gitleaks/gitleaks@latest` |
| Subfinder | `command -v subfinder` | `go install github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest` |
| Amass | `command -v amass` | `go install github.com/owasp-amass/amass/v4/...@master` |
| GAU | `command -v gau` | `go install github.com/lc/gau/v2/cmd/gau@latest` |
| Xeuledoc | `command -v xeuledoc` | `pip3 install xeuledoc` |
| MSFTRecon | `command -v msftrecon` | `pip3 install git+https://github.com/Arcanum-Sec/msftrecon.git` |
| ShareTrace | `python -m sharetrace --help 2>/dev/null` | `git clone https://github.com/7onez/sharetrace.git && cd sharetrace && pip3 install -r requirements.txt` |
| exiftool | `command -v exiftool` | `apt install -y libimage-exiftool-perl` |
| pdfinfo | `command -v pdfinfo` | `apt install -y poppler-utils` |
| oletools | `python -c "import oletools" 2>/dev/null` | `pip3 install oletools` |
| qpdf | `command -v qpdf` | `apt install -y qpdf` |
| mat2 | `command -v mat2` | `apt install -y mat2` |
| whois | `command -v whois` | `apt install -y whois` |
| dig | `command -v dig` | `apt install -y dnsutils` |
| jq | `command -v jq` | `apt install -y jq` |
| ASN | `command -v asn` | `bash <(curl -sL https://raw.githubusercontent.com/nitefood/asn/master/asn)` |
| Waymore | `command -v waymore` | `pip3 install waymore` |
| Pandoc | `command -v pandoc` | `apt install -y pandoc` |
| whoisdomain | `python -c "import whoisdomain" 2>/dev/null` | `pip3 install whoisdomain` |
| Scrapling | `python -c "import scrapling" 2>/dev/null` | `pip3 install scrapling` |
| Scrapling (full) | `python -c "from scrapling.fetchers import StealthyFetcher" 2>/dev/null` | `pip3 install "scrapling[fetchers]" && scrapling install` |
| AgentFlow | `python -c "import agentflow" 2>/dev/null` | `pip3 install agentflow-py` |

### Behavior Rules

- **Silent install:** Do not ask permission — install and proceed. Tool installation is a normal part of the investigation workflow.
- **pip vs pipx:** Use `pip` by default. Use `pipx` only for tools that explicitly require it (Sherlock).
- **Go tools:** Require Go installed. If `command -v go` fails, note the gap and fall back to next tool in cascade.
- **apt tools:** May require root. Use `sudo apt install -y` if not running as root.
- **Git-based install:** For tools without PyPI packages (ShareTrace), clone the repo and install dependencies via `git clone ... && cd ... && pip3 install -r requirements.txt`
- **Fallback on install failure:** If installation fails, skip to the next tool in the cascade — never block the investigation.
