import pytest


@pytest.fixture(scope="module")
def no_js_notify():

    def no_js_notify_handler(_: str):
        pass

    yield no_js_notify_handler
