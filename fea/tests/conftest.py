"""Shared set-up for the fea tests.

One workflow first (ADR-0089): the studio offers the unnotched tension coupon only, and the setup check refuses the other tests. Their
code, specs, checks and records stay, and these tests keep them healthy, so every test runs with the switch on unless it turns it off
itself (`tests/test_enabled.py` does, to test the refusals). Tools started as subprocesses inherit the setting.
"""

from __future__ import annotations

import pytest

from anisotropy_fea.enabled import ALL_TESTS_VARIABLE


@pytest.fixture(scope="session", autouse=True)
def every_test_offered():
    """Session-wide, so module fixtures that build a hidden test's coupon see it too; a test's own monkeypatch turns it off for itself."""
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv(ALL_TESTS_VARIABLE, "on")
        yield
