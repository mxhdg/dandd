"""Shared pytest fixtures.

Fixtures are the one place decorators live; every test keeps its own cases
inline (loops in the test body) instead of stacking parametrize decorators.
"""

import importlib.util
import shutil
import sys
from pathlib import Path

import pytest
import yaml

import app as app_module

ROOT = Path(__file__).parent.parent
SCRIPT = ROOT / "scripts" / "new_character.py"
SAMPLE = ROOT / "data" / "sample_character.yaml"


@pytest.fixture
def client(tmp_path, monkeypatch):
    # State files land directly in tmp_path; the real state/ is never touched.
    monkeypatch.setattr(app_module, "STATE_DIR", tmp_path)
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as client:
        # Real browsers send Origin on POSTs; set it here so tests reflect that
        # instead of adding it to each call site.
        client.environ_base["HTTP_ORIGIN"] = "http://localhost"
        yield client


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    """An isolated data/ directory holding only a copy of the sample character."""
    directory = tmp_path / "data"
    directory.mkdir()
    shutil.copy(SAMPLE, directory / "sample_character.yaml")
    monkeypatch.setattr(app_module, "DATA_DIR", directory)
    return directory


@pytest.fixture
def write_character(data_dir):
    """Write data/<id>.yaml from the sample with top-level overrides applied."""

    def write(character_id, **overrides):
        char = yaml.safe_load(SAMPLE.read_text(encoding="utf-8"))
        char.update({"id": character_id, **overrides})
        path = data_dir / f"{character_id}.yaml"
        path.write_text(yaml.safe_dump(char, sort_keys=False), encoding="utf-8")
        return path

    return write


@pytest.fixture
def nc():
    """scripts/new_character.py loaded as a module (it is not a package)."""
    spec = importlib.util.spec_from_file_location("new_character", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def respond(monkeypatch):
    """Script input(): respond({"substring of prompt": reply_or_list_of_replies}).

    The first key found in the prompt wins. A list is consumed one reply per
    prompt, then falls back to "" (which also ends the script's "blank to
    finish" loops). Unmatched prompts get "". Returns the prompt log.
    """

    def script(mapping=None):
        replies = {
            k: (list(v) if isinstance(v, list) else [v])
            for k, v in (mapping or {}).items()
        }
        prompts = []

        def fake_input(prompt=""):
            prompts.append(prompt)
            for key, queue in replies.items():
                if key in prompt:
                    return queue.pop(0) if queue else ""
            return ""

        monkeypatch.setattr("builtins.input", fake_input)
        return prompts

    return script


@pytest.fixture
def argv(monkeypatch):
    def set_argv(*args):
        monkeypatch.setattr(sys, "argv", ["new_character.py", *args])

    return set_argv
