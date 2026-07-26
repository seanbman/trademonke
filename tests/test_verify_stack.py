from scripts.verify_stack import endpoint_urls


def test_endpoint_urls_use_configured_or_safe_local_defaults():
    assert endpoint_urls("") == (
        "http://127.0.0.1:8000/health",
        "http://127.0.0.1:3000/",
    )
    assert endpoint_urls("PLATFORM_API_PORT=8100\nPLATFORM_GUI_PORT=3100\n") == (
        "http://127.0.0.1:8100/health",
        "http://127.0.0.1:3100/",
    )
