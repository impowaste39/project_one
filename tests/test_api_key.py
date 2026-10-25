"""Exercise require_api_key without importing app.py (which needs a database)."""
import ast
import hmac
import logging
import os
from functools import wraps

import pytest
from flask import Flask, jsonify, request


def _load_decorator():
    src = open(os.path.join(os.path.dirname(__file__), "..", "app.py")).read()
    fn = next(n for n in ast.parse(src).body
              if isinstance(n, ast.FunctionDef) and n.name == "require_api_key")
    ns = {"os": os, "hmac": hmac, "wraps": wraps, "request": request,
          "jsonify": jsonify, "logger": logging.getLogger("t")}
    exec(compile(ast.Module([fn], []), "app.py", "exec"), ns)
    return ns["require_api_key"]


@pytest.fixture
def client(monkeypatch):
    require_api_key = _load_decorator()
    app = Flask(__name__)

    @app.route("/x")
    @require_api_key
    def x():
        return jsonify(ok=True)

    return app.test_client()


def test_missing_key_is_401(client, monkeypatch):
    monkeypatch.setenv("API_WEBHOOK_KEY", "s3cret")
    assert client.get("/x").status_code == 401


def test_wrong_key_is_401(client, monkeypatch):
    monkeypatch.setenv("API_WEBHOOK_KEY", "s3cret")
    assert client.get("/x", headers={"X-API-KEY": "nope"}).status_code == 401


def test_right_key_is_200(client, monkeypatch):
    monkeypatch.setenv("API_WEBHOOK_KEY", "s3cret")
    assert client.get("/x", headers={"X-API-KEY": "s3cret"}).status_code == 200


def test_non_ascii_header_is_401_not_500(client, monkeypatch):
    monkeypatch.setenv("API_WEBHOOK_KEY", "s3cret")
    assert client.get("/x", headers={"X-API-KEY": "séc\u00e9ret".encode("utf-8")}).status_code == 401


def test_unset_server_key_fails_closed_503(client, monkeypatch):
    monkeypatch.delenv("API_WEBHOOK_KEY", raising=False)
    assert client.get("/x", headers={"X-API-KEY": "anything"}).status_code == 503
