"""Lab Status aggregate API."""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from ..services import lab_status_service

bp = Blueprint("lab_status", __name__)


@bp.route("/api/lab-status/overview", methods=["GET"])
def lab_status_overview():
    try:
        window_minutes = int(request.args.get("window_minutes", 120))
    except (TypeError, ValueError):
        return jsonify({"error": "window_minutes must be an integer"}), 400

    try:
        return jsonify(lab_status_service.build_overview(window_minutes=window_minutes))
    except Exception as exc:
        return jsonify({"error": f"Failed to build lab status overview: {exc}"}), 500
