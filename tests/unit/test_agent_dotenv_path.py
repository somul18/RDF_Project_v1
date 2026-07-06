"""Regression tests for the portable project-root .env resolution in the
extractor/critic agents (previously hardcoded to an absolute path on a
different machine/project directory).
"""
import importlib
import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_SRC_DIR = os.path.join(_REPO_ROOT, "src")
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

import agents.critic_agent as critic_agent
import agents.extractor_agent as extractor_agent

_MODULES = (extractor_agent, critic_agent)


def test_project_root_resolves_to_repo_root():
    for module in _MODULES:
        assert module._PROJECT_ROOT == _REPO_ROOT


def test_project_root_is_a_real_project_directory():
    for module in _MODULES:
        assert os.path.isfile(os.path.join(module._PROJECT_ROOT, "pyproject.toml"))


def test_no_hardcoded_user_specific_path_in_source():
    """Regression guard: don't reintroduce a machine-specific absolute dotenv path."""
    for module in _MODULES:
        with open(module.__file__, encoding="utf-8") as f:
            source = f.read()
        assert "/Users/" not in source, (
            f"{module.__name__} contains a hardcoded user-specific absolute path"
        )


def test_project_root_independent_of_cwd(tmp_path, monkeypatch):
    """The resolved root must derive from __file__, not the current working directory."""
    monkeypatch.chdir(tmp_path)
    for module in _MODULES:
        importlib.reload(module)
        assert module._PROJECT_ROOT == _REPO_ROOT
