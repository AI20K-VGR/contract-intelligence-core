# Command Reference

## 3. Command Reference

Commands grouped by AEAD phase.

### Acquire

| Command | What It Does | Example |
|---------|-------------|---------|
| `/case [target]` | Full pipeline — runs every applicable technique | `/case example.com` |
| `/sweep [target]` | Multi-vector recon on any target type | `/sweep @username` |
| `/query [subject]` | Builds 12–15 advanced search operator queries | `/query example.com` |
| `/username [handle]` | Enumerate handle across 3000+ platforms | `/username johndoe` |
| `/phone [number]` | Carrier, line type, reputation, public associations | `/phone +84901234567` |
| `/email-deep [email]` | Accounts, breach history, infrastructure | `/email-deep u@domain.com` |
| `/subdomain [domain]` | CT logs, brute-force, passive enumeration | `/subdomain example.com` |
| `/breach-deep [email]` | Multi-source breach lookup with context | `/breach-deep u@domain.com` |
| `/traffic [domain]` | Traffic estimation, ranking, audience data | `/traffic example.com` |
| `/visitors [domain]` | Full visitor intelligence: tech, geo, sources, analytics | `/visitors example.com` |
| `/techstack [domain]` | Technology fingerprint (CMS, analytics, CDN, server) | `/techstack example.com` |
| `/competitors [domain]` | Competitor & related site discovery | `/competitors example.com` |
| `/secrets [target]` | Exposed credentials in repos and paste sites | `/secrets github.com/org` |
| `/github-osint [target]` | GitHub profile, org, repo, code, commit metadata, and collaboration recon | `/github-osint github.com/org/repo` |
| `/threat-check [target]` | IP/domain/URL/hash threat intelligence | `/threat-check 185.1.1.1` |
| `/scam-check [domain]` | Phishing/scam/malicious domain check | `/scam-check susp-site.xyz` |
| `/vuln-check [query]` | CVE/vulnerability lookup (CIRCL + NVD) | `/vuln-check CVE-2024-1234` or `/vuln-check apache/httpd` |
| `/ransomware-check [org]` | Check if org is a ransomware victim | `/ransomware-check "Acme Corp"` |
| `/gdoc [url]` | Extract metadata/owner from Google document | `/gdoc https://docs.google.com/...` |
| `/msftrecon [domain]` | M365/Azure tenant recon — tenant ID, federation, MDI, SharePoint | `/msftrecon example.com` |
| `/sharelink [url]` | Extract sharer identity from share link | `/sharelink https://vm.tiktok.com/ABC` |
<!-- dork-integration:phase-05 start -->
| `/dork-sweep [target] [--telegram\|--docs\|--filetype\|--all] [--after DATE] [--clean]` | Zero-auth dork sweep: Telegram ecosystem, 18 doc-hosts, filetype families; 4-tier fallback cascade | `/dork-sweep example.com --filetype` |
| `/docleak [target] [--platform list] [--severity high]` | 18-platform document leak hunt with severity classification (CRITICAL/HIGH/MEDIUM/LOW) | `/docleak "Acme Corp"` |
<!-- dork-integration:phase-05 end -->
| `/dns-history [domain]` | Historical DNS record changes (A, NS, MX) via passive DNS | `/dns-history example.com` |
| `/cert-history [domain]` | SSL/TLS certificate timeline from CT logs (crt.sh) | `/cert-history example.com` |
| `/email-permute [name] [domain]` | Generate email permutations from name + domain | `/email-permute "John Smith" company.com` |
| `/proton-check [email]` | Proton Mail account creation date via PGP key | `/proton-check user@proton.me` |
| `/pgp-lookup [email]` | PGP key search — creation date, UIDs, signatures | `/pgp-lookup dev@example.com` |
| `/wifi [ssid]` | WiFi SSID geolocation via Wigle.net | `/wifi "HomeNetwork"` |
| `/wifi --bssid [mac]` | Exact AP lookup by MAC address | `/wifi --bssid AA:BB:CC:DD:EE:FF` |
| `/register [name]` | Add a subject to the case workspace | `/register JohnDoe` |
| `/snapshots [url]` | View archived Wayback snapshots of a URL | `/snapshots example.com` |

### Enrich

| Command | What It Does | Example |
|---------|-------------|---------|
| `/branch [data]` | Expand a discovered identifier laterally | `/branch john@mail.com` |
| `/timeline [subject]` | Assemble dated event sequence | `/timeline Company Inc` |
| `/crossref` | Detect shared identifiers across subjects | `/crossref` |
| `/link-subjects [A] [B]` | Define a connection between two subjects | `/link-subjects John Jane` |
| `/show-connections` | Display all logged connections | `/show-connections` |
| `/show-trail [subject]` | Show the evidence chain for a subject | `/show-trail JohnDoe` |
| `/watch [subject]` | Add subject to active tracking list | `/watch example.com` |
| `/record-finding` | Log a finding with source and confidence | Paste data after command |
| `/show-findings` | List all recorded findings | `/show-findings` |
| `/graph` | Full ASCII subject relationship map | `/graph` |
| `/pathfind [A] [B]` | Discover connection path between subjects | `/pathfind A B` |
| `/diff [url]` | Diff archived versions of a URL | `/diff example.com/page` |

### Assess

| Command | What It Does | Example |
|---------|-------------|---------|
| `/exposure [target]` | Composite exposure score (0–100) | `/exposure domain.com` |
| `/threat-model` | Build threat model from findings | `/threat-model` |
| `/signatures` | Surface recurring behavioral patterns | `/signatures` |
| `/validate` | Quality audit — score 0–100 | `/validate` |
| `/coverage` | Coverage matrix with identified gaps | `/coverage` |
| `/verify-finding [id]` | Re-check a specific finding's sources | `/verify-finding 12` |
| `/subject [name]` | View or create subject record | `/subject JohnDoe` |
| `/lookup [name]` | Retrieve a registered subject | `/lookup JohnDoe` |
| `/modify [name]` | Update a subject record | `/modify JohnDoe` |
| `/archive-subject [name]` | Remove subject from active tracking | `/archive-subject JohnDoe` |
| `/find [query]` | Search across all subjects | `/find domain:example.com` |
| `/show-trail [subject]` | Full evidence trail | `/show-trail JohnDoe` |
| `/blind-spots` | Prioritized investigation gap analysis | `/blind-spots` |
| `/source-check` | Batch source URL accessibility check | `/source-check` |
| `/drift [subject]` | Temporal risk score tracking | `/drift example.com` |
| `/clarify [finding]` | Plain-language finding explanation | `/clarify fnd-003` |

### Deliver

| Command | What It Does | Example |
|---------|-------------|---------|
| `/report` | Formal structured intelligence report | `/report` |
| `/report brief` | Single-page executive brief | `/report brief` |
| `/report json` | Raw data as JSON | `/report json` |
| `/report csv` | Spreadsheet-compatible export | `/report csv` |
| `/report legal` | Evidence-formatted for legal proceedings | `/report legal` |
| `/report journalist` | Source-citation-heavy format | `/report journalist` |
| `/brief` | Plain-language summary (non-technical) | `/brief` |
| `/render entities` | ASCII subject relationship diagram | `/render entities` |
| `/render timeline` | Chronological event chart | `/render timeline` |
| `/render risk` | Exposure heatmap | `/render risk` |
| `/render network` | Network topology of connections | `/render network` |
| `/stats` | Counts and coverage statistics | `/stats` |
| `/workspace save [name]` | Persist case state | `/workspace save mycase` |
| `/workspace open [name]` | Resume a saved case | `/workspace open mycase` |
| `/workspace list` | Show saved cases | `/workspace list` |
| `/workspace diff [a] [b]` | Diff two saved workspaces | `/workspace diff case1 case2` |
| `/render threat-path` | ASCII attack path flow diagram | `/render threat-path` |
| `/render attack-surface` | ASCII attack surface exposure map | `/render attack-surface` |
| `/report ioc` | Export IOCs as STIX 2.1 or flat list | `/report ioc --format stix` |

### UX & Navigation

| Command | What It Does | Example |
|---------|-------------|---------|
| `/flow [type]` | Guided step-by-step case workflow | `/flow person` |
| `/template list` | Browse pre-built case templates | `/template list` |
| `/template run [name]` | Run a pre-built template | `/template run security-audit` |
| `/novice` | Toggle simplified, low-jargon mode | `/novice` |
| `/terms` | OSINT term glossary | `/terms` |
| `/progress` | Current case phase and coverage | `/progress` |
| `/opsec` | OPSEC checklist for current task | `/opsec` |
| `/onboard` | Interactive first-time onboarding guide | `/onboard` |
| `/quality` | Investigation quality composite score | `/quality` |

---

