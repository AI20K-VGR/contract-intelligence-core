from __future__ import annotations

from app.contracts.models import ObjectRoute, ToolEnvelope
from app.tools.gateway import ToolGateway


class ObjectRouter:
    def __init__(self, gateway: ToolGateway) -> None:
        self.gateway = gateway

    def scout(self, envelope: ToolEnvelope) -> list[dict]:
        return self.gateway.call("list_structure", envelope, dossier_id=envelope.auth.dossier_id)

    def route_node(self, node: dict) -> ObjectRoute:
        ntype = node.get("type")
        if ntype == "TABLE":
            return ObjectRoute.TABLE
        if ntype == "FIELD":
            return ObjectRoute.FIELD
        if ntype in {"CLAUSE", "SECTION", "UNNUMBERED_BLOCK"}:
            return ObjectRoute.CLAUSE
        return ObjectRoute.CLAUSE
