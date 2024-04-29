import pytest


@pytest.fixture(scope="module")
def no_js_notify():
    """Fixture to not care about notification of detection of a JS file"""

    def no_js_notify_handler(_: str):
        pass

    yield no_js_notify_handler
