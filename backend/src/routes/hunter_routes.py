"""Hunter report API routes."""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from ..services import agent_service, hunter_reports


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

    @bp.route("/hunter/missions", methods=["GET"])
    def list_hunter_missions():
        limit = request.args.get("limit", default=20, type=int)
        missions = hunter_reports.list_missions(limit=max(limit, 1))
        return jsonify({"missions": missions, "count": len(missions)})

    @bp.route("/hunter/missions/<mission_id>", methods=["GET"])
    def get_hunter_mission(mission_id: str):
        mission = hunter_reports.mission_by_id(mission_id)
        if mission is None:
            return jsonify({"error": "Mission not found"}), 404
        report = None
        report_id = mission.get("reportId")
        if report_id:
            report = hunter_reports.normalized_run_by_id(report_id)
        return jsonify({"mission": mission, "report": report})

    @bp.route("/hunter/missions", methods=["POST"])
    def spawn_hunter_mission():
        payload = request.get_json(silent=True) or {}
        if not isinstance(payload, dict):
            return jsonify({"error": "JSON body required"}), 400
        result = agent_service.spawn_mission(payload)
        status_code = 202 if result.get("status") == "started" else 400
        if result.get("status") == "skipped":
            status_code = 503
        return jsonify(result), status_code

    return bp
