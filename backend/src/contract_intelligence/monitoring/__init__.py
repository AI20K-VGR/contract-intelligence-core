"""Admin monitoring — Grafana behind /grafana and Prometheus metrics.

    session.py       — short-lived /grafana cookie minted from a Keycloak token
    grafana_proxy.py — /grafana/* reverse proxy: ADMINISTRATOR check, then
                       Grafana auth-proxy headers set by the backend only
    metrics.py       — HTTP metrics + internal-only Prometheus endpoint

Metric labels carry route templates, methods and status classes only — never
dossier content, file names, user identity or tokens.
"""
