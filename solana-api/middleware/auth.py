# -*- coding: utf-8 -*-
from functools import wraps
from flask import current_app, request, jsonify

def require_api_key(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_app.config.get("REQUIRE_AUTH", False):
            return fn(*args, **kwargs)
        expected = (current_app.config.get("API_KEY") or "").strip()
        got = (request.headers.get("Authorization") or "").strip()
        if got.startswith("Bearer "):
            got = got.split(" ", 1)[1]
        if not expected or got != expected:
            return jsonify({"ok": False, "error": "unauthorized"}), 401
        return fn(*args, **kwargs)
    return wrapper
