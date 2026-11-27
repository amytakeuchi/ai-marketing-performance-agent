import pytest

from mpia import config

pytestmark = pytest.mark.db


def test_streamlit_app_renders_and_answers(api):
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(config.ROOT / "mpia" / "app" / "streamlit_app.py"), default_timeout=90).run()
    assert not at.exception
    at.text_input(key="q").set_value("Why did Meta ROAS decline in October compared with September?")
    at.button[[b.label for b in at.button].index("Investigate")].click().run()
    assert not at.exception and "fell" in at.subheader[0].value
