"""Hunter report API routes."""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from ..services import hunter_reports


def create_hunter_blueprint():
    bp = Blueprint("hunter", __name__)

    @bp.route("/hunter/runs", methods=["GET"])
    def get_hunter_runs():
        limit = request.args.get("limit", default=20, type=int)
        runs = hunter_reports.list_normalized_runs(limit=max(limit, 1))
        return jsonify({
            "runs": runs,
            "count": len(runs),
        })

    @bp.route("/hunter/runs/latest", methods=["GET"])
    def get_latest_hunter_run():
        run = hunter_reports.latest_normalized_run()
        if run is None:
            return jsonify({"error": "No hunter runs found"}), 404
        return jsonify(run)

    @bp.route("/hunter/runs/<path:run_id>", methods=["GET"])
    def get_hunter_run(run_id: str):
        run = hunter_reports.normalized_run_by_id(run_id)
        if run is None:
            return jsonify({"error": "Hunter run not found"}), 404
        return jsonify(run)

    @bp.route("/hunter/overview", methods=["GET"])
    def get_hunter_overview():
        limit = request.args.get("limit", default=20, type=int)
        payload = hunter_reports.hunter_overview(limit=max(limit, 1))
        return jsonify(payload)

    return bp
