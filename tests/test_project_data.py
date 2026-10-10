"""Shipped data files: small, valid, with provenance, and named literally in the code."""
import ast
import os

import pytest

import qk_data

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT = os.path.join(ROOT, "qollab_project")
DATA = os.path.join(PROJECT, "data")


def _literal_strings():
    found = set()
    for name in os.listdir(PROJECT):
        if name.endswith(".py"):
            tree = ast.parse(open(os.path.join(PROJECT, name)).read())
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    found.add(os.path.normpath(node.value))
    return found


DATA_FILES = sorted(f for f in os.listdir(DATA) if not f.startswith("."))


@pytest.mark.parametrize("name", DATA_FILES)
def test_data_file_valid_small_and_literal(name):
    path = os.path.join(DATA, name)
    text = open(path).read()
    assert len(text.encode()) <= 300_000
    d = qk_data.parse_dataset(text)
    assert d["machine"] == qk_data.MACHINE and d["git_commit"] not in ("", "unknown")
    assert os.path.normpath("data/" + name) in _literal_strings(), "not named literally: " + name


def test_chsh_noise_dataset_content():
    d = qk_data.parse_dataset(open(os.path.join(DATA, "chsh_noise.json")).read())
    assert abs(d["results"]["derived"]["lambda_star_numeric"] - (1 - 2 ** -0.5)) < 1e-8
    rows = d["results"]["rows"]
    assert len(rows) == 71 and abs(rows[0]["S"] - 2 * 2 ** 0.5) < 1e-12
