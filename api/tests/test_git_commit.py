"""records.git_commit: the repository's commit when the code sits in a checkout, else the commit the solver image was built from
(ANISOTROPY_GIT_COMMIT, ADR-0056), else None; a malformed variable is refused, not ignored (ADR-0003)."""

import re

import pytest

from anisotropy_api.records import COMMIT_VARIABLE, git_commit

HEX40 = re.compile(r"^[0-9a-f]{40}$")
COMMIT = "0123456789abcdef0123456789abcdef01234567"


def test_a_checkout_gives_its_head_and_ignores_the_variable():
    found = git_commit(environ={COMMIT_VARIABLE: COMMIT})
    assert found is None or HEX40.match(found)  # None only where git is absent
    if found is not None:
        assert found != COMMIT


def test_outside_a_checkout_the_variable_gives_the_commit(tmp_path):
    assert git_commit(environ={COMMIT_VARIABLE: COMMIT}, cwd=tmp_path) == COMMIT
    assert git_commit(environ={COMMIT_VARIABLE: f"  {COMMIT.upper()}  "}, cwd=tmp_path) == COMMIT


def test_outside_a_checkout_without_the_variable_there_is_no_commit(tmp_path):
    assert git_commit(environ={}, cwd=tmp_path) is None
    assert git_commit(environ={COMMIT_VARIABLE: "   "}, cwd=tmp_path) is None


@pytest.mark.parametrize("value", ["main", "0123456", "0123456789abcdef0123456789abcdef0123456g", COMMIT + "0"])
def test_a_malformed_variable_is_refused(tmp_path, value):
    with pytest.raises(RuntimeError, match=COMMIT_VARIABLE):
        git_commit(environ={COMMIT_VARIABLE: value}, cwd=tmp_path)
