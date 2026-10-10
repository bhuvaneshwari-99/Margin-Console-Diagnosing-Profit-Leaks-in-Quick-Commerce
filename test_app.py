"""Headless UI smoke tests: drive the real Streamlit script through its modes and assert no exceptions."""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parent.parent / "streamlit_app.py")


def run(setup=None):
    at = AppTest.from_file(APP, default_timeout=120).run()
    if setup:
        setup(at)
        at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def test_default_view_renders():
    at = run()
    assert len(at.metric) >= 5 and len(at.tabs) == 6
    assert "Margin Console" in at.title[0].value


def test_zero_threshold_is_baseline():
    at = run(lambda a: a.sidebar.slider[0].set_value(0))
    assert at.metric[1].value == "₹0"          # change in profit


def test_fee_mode_and_low_margin():
    at = run(lambda a: a.sidebar.radio[0].set_value("Small-order fee"))
    labels = [x.label for x in at.sidebar.slider]
    assert "Flat fee (₹)" in labels
    def stress(a):
        a.sidebar.radio[0].set_value("Small-order fee")
        a.sidebar.slider[0].set_value(300)
        a.sidebar.slider[[x.label for x in a.sidebar.slider].index("Contribution per ₹ of basket")].set_value(25)
    at = run(stress)
    assert at.metric[2].value.endswith("%")


def test_city_subset_and_empty_selection():
    at = run(lambda a: a.sidebar.multiselect[1].set_value(["Delhi", "Pune"]))
    assert not at.error
    at = AppTest.from_file(APP, default_timeout=120).run()
    at.sidebar.multiselect[0].set_value([]).run()
    assert at.error and not at.exception      # graceful message, no crash
