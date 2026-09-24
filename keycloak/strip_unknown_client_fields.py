"""Strip forward-compat client fields from realm-export.json.

Background:
    realm-export.json was generated from a newer Keycloak build that contains
    fields (`postLogoutRedirectUris`, `accessTokenResponseIssueStatement`, …)
    which Keycloak 26.7.4's strict Jackson ObjectMapper refuses to deserialize.

    The `QUARKUS_JACKSON_FAIL_ON_UNKNOWN_PROPERTIES=false` env only affects
    REST endpoint deserialization, NOT `RealmRepresentation` import in
    `DirImportProvider` — that path uses its own ObjectMapper with strict mode.

    This script keeps ONLY the fields that appear in the Jackson error message
    (the 44 "known properties") on each client object. Unknown fields are
    silently dropped. Safe because we're only discarding *fields the running
    version doesn't understand*, not modifying semantics.

Usage:
    python strip_unknown_client_fields.py keycloak/realm-export.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# 44 known ClientRepresentation properties (from Keycloak 26.7.4 error message).
KNOWN_CLIENT_FIELDS: set[str] = {
    "access",
    "adminUrl",
    "alwaysDisplayInConsole",
    "attributes",
    "authenticationFlowBindingOverrides",
    "authorizationServicesEnabled",
    "authorizationSettings",
    "baseUrl",
    "bearerOnly",
    "clientAuthenticatorType",
    "clientId",
    "consentRequired",
    "defaultClientScopes",
    "defaultRoles",
    "description",
    "directAccessGrantsEnabled",
    "directGrantsOnly",
    "enabled",
    "frontchannelLogout",
    "fullScopeAllowed",
    "id",
    "implicitFlowEnabled",
    "name",
    "nodeReregistrationTimeout",
    "notBefore",
    "optionalClientScopes",
    "origin",
    "protocol",
    "protocolMappers",
    "publicClient",
    "redirectUris",
    "registeredNodes",
    "registrationAccessToken",
    "rootUrl",
    "secret",
    "serviceAccountsEnabled",
    "standardFlowEnabled",
    "surrogateAuthRequired",
    "type",
    "useTemplateConfig",
    "useTemplateMappers",
    "useTemplateScope",
    "webOrigins",
}


def strip_unknown_client_fields(realm: dict[str, object]) -> tuple[dict[str, object], int]:
    """Strip fields not in KNOWN_CLIENT_FIELDS from each client object.

    Returns:
        Tuple of (cleaned_realm, dropped_field_count).
    """
    clients = realm.get("clients")
    if not isinstance(clients, list):
        return realm, 0

    dropped = 0
    cleaned_clients: list[object] = []
    for client in clients:
        if not isinstance(client, dict):
            cleaned_clients.append(client)
            continue
        kept: dict[str, object] = {}
        for key, value in client.items():
            if key in KNOWN_CLIENT_FIELDS:
                kept[key] = value
            else:
                dropped += 1
                print(f"  - Dropping unknown client field: {key!r}")
        cleaned_clients.append(kept)

    realm["clients"] = cleaned_clients
    return realm, dropped


def main() -> int:
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <realm-export.json>")
        return 2

    path = Path(sys.argv[1])
    with path.open(encoding="utf-8") as fh:
        realm = json.load(fh)

    cleaned, dropped = strip_unknown_client_fields(realm)
    print(f"Dropped {dropped} unknown client field(s).")

    with path.open("w", encoding="utf-8") as fh:
        json.dump(cleaned, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    print(f"Wrote cleaned realm to {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
