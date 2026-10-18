"""Smoke test for the Streamlit demo: run the whole script against a recording stub,
so CI catches API drift in abtrust without needing a browser or Streamlit itself."""

import runpy
import sys
import types
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app" / "streamlit_app.py"


class _Ctx:
    """Tabs and columns: context managers that also expose the streamlit API (``col.metric(...)``)."""

    def __init__(self, st):
        self._st = st

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def __getattr__(self, name):
        return getattr(self._st, name)


def _make_stub(calls, overrides=None):
    overrides = overrides or {}
    st = types.ModuleType("streamlit")

    def record(name):
        return lambda *a, **k: calls.append((name, a[0] if a else None))

    for name in (
        "set_page_config",
        "title",
        "caption",
        "markdown",
        "dataframe",
        "image",
        "info",
        "error",
        "success",
        "warning",
        "download_button",
    ):
        setattr(st, name, record(name))
    st.tabs = lambda names: [_Ctx(st) for _ in names]
    st.columns = lambda n: [_Ctx(st) for _ in range(n if isinstance(n, int) else len(n))]
    st.radio = lambda label, options, index=0, **k: overrides.get(label, options[index])
    st.selectbox = lambda label, options, index=0, **k: options[index]
    st.multiselect = lambda label, options, default=None, **k: list(overrides.get(label, default or []))
    st.checkbox = lambda label, value=False, **k: value
    st.number_input = lambda label, min_value=None, max_value=None, value=None, **k: overrides.get(k.get("key", label), value)
    st.text_input = lambda label, value="", **k: overrides.get(k.get("key", label), value)
    st.slider = lambda label, min_value=None, max_value=None, value=None, **k: value
    st.button = lambda label, **k: True
    st.file_uploader = lambda *a, **k: overrides.get("_upload")
    st.metric = lambda label, value, *a, **k: calls.append(("metric", (label, value)))
    st.cache_data = lambda f=None, **k: f if f else (lambda g: g)
    st.session_state = {}
    return st


def test_app_runs_end_to_end(monkeypatch):
    calls = []
    monkeypatch.setitem(sys.modules, "streamlit", _make_stub(calls))
    runpy.run_path(str(APP), run_name="__main__")
    names = [c[0] for c in calls]
    assert "error" not in names
    assert "image" in names and "download_button" in names
    metrics = dict(c[1] for c in calls if c[0] == "metric")
    assert metrics["Users per arm"] == "57,760"
    assert float(metrics["Naive t-test false positives"].rstrip("%")) > 10


class _Upload:
    def __init__(self, content):
        self.content = content

    def getvalue(self):
        return self.content


def _run_with(monkeypatch, overrides):
    calls = []
    monkeypatch.setitem(sys.modules, "streamlit", _make_stub(calls, overrides))
    runpy.run_path(str(APP), run_name="__main__")
    return calls


def test_dashboard_custom_unequal_split_and_valid_csv(monkeypatch):
    upload = b"user_id,variant,converted,complaints\n" + b"".join(
        f"{i},{'control' if i < 20 else 'treatment'},{i % 2},0\n".encode() for i in range(100)
    )
    calls = _run_with(monkeypatch, {
        "Data": "Upload a CSV", "_upload": _Upload(upload),
        "Expected allocation from the experiment design": "Custom allocation (%)",
        "allocation_control": 20.0, "allocation_treatment": 80.0,
    })
    msgs = [v for n, v in calls if n in {"success", "error", "info"}]
    assert any("SRM check passed" in str(v) for v in msgs)
    assert not any("SRM check FAILED" in str(v) for v in msgs)
    assert "download_button" in [n for n, _ in calls]


def test_dashboard_invalid_allocation_blocks_analysis(monkeypatch):
    calls = _run_with(monkeypatch, {
        "Expected allocation from the experiment design": "Custom allocation (%)",
        "allocation_control": 40.0, "allocation_treatment": 40.0,
    })
    assert any("must total 100" in str(v) for n, v in calls if n == "error")
    assert "download_button" not in [n for n, _ in calls]


def test_dashboard_invalid_csv_does_not_crash(monkeypatch):
    calls = _run_with(monkeypatch, {"Data": "Upload a CSV", "_upload": _Upload(b"bad")})
    assert "error" in [n for n, _ in calls]
    assert "download_button" not in [n for n, _ in calls]


def test_dashboard_invalid_harm_margin_blocks_analysis(monkeypatch):
    calls = _run_with(monkeypatch, {"margin_unsubscribed": "not-a-number"})
    assert any("provide a numeric" in str(v) for n, v in calls if n == "error")
    assert "download_button" not in [n for n, _ in calls]


def test_dashboard_invalid_planning_rate_does_not_crash(monkeypatch):
    calls = _run_with(monkeypatch, {"Baseline rate": 0.9, "Relative MDE": 0.2})
    assert any("planned treatment rate" in str(v) for n, v in calls if n == "error")
    assert "Users per arm" not in dict(v for n, v in calls if n == "metric")
    # An invalid plan must not prevent analysis or the peeking tab from rendering.
    assert "download_button" in [n for n, _ in calls]
    assert "Sequential procedure false positives" in dict(v for n, v in calls if n == "metric")


def test_dashboard_confidence_label_tracks_analysis_alpha(monkeypatch):
    calls = _run_with(monkeypatch, {"analysis_alpha": 0.1})
    captions = [str(v) for n, v in calls if n == "caption"]
    assert any("Unadjusted 90% CIs" in v for v in captions)
    assert not any("Unadjusted 95% CIs" in v for v in captions)
