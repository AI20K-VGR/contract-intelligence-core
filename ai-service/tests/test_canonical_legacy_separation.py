from app.api.main import app


def test_legacy_ocr_endpoint_is_explicitly_non_canonical() -> None:
    route = next(route for route in app.routes if getattr(route, "path", "") == "/api/v1/jobs/ocr")
    assert route.status_code == 501

