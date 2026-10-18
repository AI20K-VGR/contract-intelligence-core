import pytest
from pydantic import ValidationError

from contract_intelligence.schemas.queries import DossierQueryRequest


@pytest.mark.parametrize("query", ["", " ", "\t\r\n", "\u00a0\u2003"])
def test_blank_queries_are_rejected_before_forwarding_to_ai2(query):
    with pytest.raises(ValidationError):
        DossierQueryRequest(query=query)


def test_query_trims_only_the_surrounding_whitespace():
    assert DossierQueryRequest(query="  Điều 5\nbao gồm gì? \n").query == "Điều 5\nbao gồm gì?"
