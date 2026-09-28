# Technique Catalog & Workflow Guides

## 6. Technique Catalog

Reference directory: `techniques/`

| File | Covers |
|------|--------|
| `fx-metadata-parsing.md` | EXIF, email headers, document metadata analysis |
| `fx-image-verification.md` | Image authenticity and provenance workflow |
| `fx-breach-discovery.md` | Breach database methods and paste site search |
| `fx-geolocation.md` | GPS extraction, W3W, Plus Codes, MGRS, Street View |
| `fx-social-topology.md` | Social graph construction and topology |
| `fx-email-header-analysis.md` | Header analysis, SPF/DKIM, SMTP routing |
| `fx-document-forensics.md` | Document forensics and metadata extraction |
| `fx-http-fingerprint.md` | HTTP fingerprinting and server signature analysis |
| `fx-leak-monitoring.md` | Leak and breach monitoring, paste site search |
<!-- dork-integration:phase-05 start -->
| `fx-dork-sweep.md` | Zero-auth Google/Bing dork sweeps — Telegram ecosystem, doc-hosts, filetype families + 4-tier fallback cascade (WebSearch → Bing → DDG → agent-browser) |
| `fx-document-leak-hunt.md` | 18-platform document leak discovery with severity classification, paywall handling, auto-snapshot |
<!-- dork-integration:phase-05 end -->
| `username-osint.md` | 3000+ platform enumeration with pivot extraction |
| `phone-osint.md` | Carrier lookup, VoIP detection, spam databases, FreeCNAM CallerID, WhoCalld, USPhoneBook reverse lookup |
| `email-osint.md` | Full email investigation: accounts, breaches, infra, Proton API, PGP keys, permutation, manual reference tools |
| `fx-dns-cert-history.md` | Historical DNS records (passive DNS, A/NS/MX changes), SSL certificate timeline (crt.sh CT logs) |
| `threat-intel.md` | AbuseIPDB, GreyNoise, OTX, VirusTotal, **URLScan.io**, **CIRCL CVE**, **NVD API**, **ransomware.live** |
| `web-traffic-analysis.md` | SimilarWeb/Semrush estimation, audience data |
| `secret-scanning.md` | Credential/secret detection in repos and pastes |
| `domain-advanced.md` | Subfinder, Amass, CT log enumeration |
| `social-media-platforms.md` | Twitter/X Snowflake IDs, Discord, Strava, BlueSky, ShareTrace share link analysis |
| `advanced-geolocation-techniques.md` | Overpass Turbo, road sign analysis, reflected text |
| `web-dns-forensics.md` | Zone transfers, Tor lookups, GitHub, Telegram, WHOIS, Xeuledoc Google doc intel |
| `fx-visitor-intelligence.md` | Visitor stats, tech stack, geo, traffic sources, analytics/AdSense/advertising ID cross-domain linking, competitors |
| `wifi-ssid-osint.md` | WiFi SSID/BSSID geolocation via Wigle.net, encryption analysis, travel patterns |
| `scam-check.md` | Phishing/scam domain verification and detection |
| `cloud-audit.md` | Cloud infrastructure security (AWS/GCP/Azure): IAM, network, storage, compute, logging, secrets |
| `microsoft-tenant-recon.md` | M365/Azure tenant enumeration — federation, tenant ID, Azure AD config, MDI detection |
| `dependency-audit.md` | Supply chain security: CVE audit, framework-specific vulns, typosquatting, CI/CD security |
| `disk-forensics.md` | Digital evidence analysis: image integrity, Sleuth Kit, file carving, artifact recovery, timeline |
| `incident-triage.md` | Security incident response: NIST 800-61 methodology, containment, evidence preservation, IOC extraction |
| `owasp-audit.md` | OWASP Top 10 (2021) source code audit with grep patterns and CWE references |
| `prompt-injection-audit.md` | AI/LLM security: prompt injection classes, agent/MCP security, permission boundary audit |

---

## 7. Workflow Guides

Reference directory: `workflows/`

| Guide | Intended User | File |
|-------|--------------|------|
| Journalist Source Verification | Journalists verifying claims | `wf-journalist.md` |
| HR Screening | HR professionals running background checks | `wf-hr-screening.md` |
| Cyber Threat Intelligence | Security analysts tracking adversaries | `wf-threat-analyst.md` |
| Private Investigator | Licensed PIs running person cases | `wf-private-investigator.md` |

Activate via `/flow [type]` — guided prompts walk through each step.

---

