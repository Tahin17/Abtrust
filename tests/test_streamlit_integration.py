"""Optional real-Streamlit smoke test; enabled in the CI app-smoke job.

File uploads and negative input paths are covered by test_app.py and
app_support tests; upload controls are not fully supported by AppTest.
"""

import os
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "app" / "streamlit_app.py"


@pytest.mark.skipif(os.environ.get("ABTRUST_RUN_STREAMLIT_INTEGRATION") != "1",
                    reason="real Streamlit UI test enabled in the CI app-smoke job")
def test_real_streamlit_sample_dashboard():
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest

    page = AppTest.from_file(str(APP), default_timeout=40).run()
    assert not page.exception, [str(x.message) for x in page.exception]
    assert any("abtrust" in str(t.value).lower() for t in page.title)
    assert page.get("dataframe")  # The sample data / statistical table renders

    page.number_input(key="analysis_alpha").set_value(0.1).run()
    assert not page.exception
    assert any("Unadjusted 90% CIs" in str(c.value) for c in page.caption)

    next(w for w in page.number_input if w.label == "Baseline rate").set_value(0.9)
    next(w for w in page.number_input if w.label == "Relative MDE").set_value(0.2)
    page.run()
    assert not page.exception
    assert any("planned treatment rate" in str(e.value) for e in page.error)
    assert not any(m.label == "Users per arm" for m in page.metric)

    next(w for w in page.number_input if w.label == "Baseline rate").set_value(0.1)
    next(w for w in page.number_input if w.label == "Relative MDE").set_value(0.05)
    page.run()
    assert not page.exception and not page.error
    assert any(m.label == "Users per arm" and m.value == "57,760" for m in page.metric)
