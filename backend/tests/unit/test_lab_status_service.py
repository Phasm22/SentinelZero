import json
from datetime import datetime, timedelta
from unittest.mock import patch

from app import db
from src.models import SensorAgent, SensorTelemetry
from src.services import lab_status_service


def setup_function():
    lab_status_service.clear_cache()


def test_normalize_ntop_active_hosts_accepts_dict_shape():
    payload = {
        "total_active": 4,
        "flagged": [
            {"ip": "172.16.0.10", "score": 12, "num_alerts": 1},
            {"ip": "172.16.0.11", "score": 80, "num_alerts": 0},
        ],
    }

    result = lab_status_service.normalize_ntop_active_hosts(payload)

    assert result["total_active"] == 4
    assert result["flagged_count"] == 2
    assert result["flagged"][0]["ip"] == "172.16.0.11"


def test_normalize_ntop_active_hosts_accepts_legacy_list_shape():
    payload = [
        {"ip": "172.16.0.10", "score": {"total": 0}, "num_alerts": 0},
        {"ip": "172.16.0.11", "score": {"total": 42}, "num_alerts": 0},
        {"ip": "172.16.0.12", "score": 0, "num_alerts": 2},
    ]

    result = lab_status_service.normalize_ntop_active_hosts(payload)

    assert result["total_active"] == 3
    assert [host["ip"] for host in result["flagged"]] == ["172.16.0.11", "172.16.0.12"]


def test_normalize_pihole_payload_caps_and_maps_summary():
    payload = {
        "summary": {"total": 1000, "blocked": 350, "percent_blocked": "35.0"},
        "top_clients": [{"client": f"host-{idx}", "count": idx} for idx in range(12)],
        "top_domains": {"example.test": 9},
        "top_blocked": [{"domain": "ads.test", "count": 5}],
    }

    result = lab_status_service.normalize_pihole_payload(payload, source="lab")

    assert result["summary"]["total_queries"] == 1000
    assert result["summary"]["percent_blocked"] == 35.0
    assert len(result["top_clients"]) == 10
    assert result["top_domains"][0]["name"] == "example.test"


def test_normalize_opnsense_payload_summarizes_inventory_and_alerts():
    payload = {
        "gateway_status": [{"name": "WAN", "status": "offline"}],
        "dhcp_leases": [
            {"ip": "172.16.0.10", "status": "online"},
            {"ip": "172.16.0.11", "status": "offline"},
        ],
        "arp_table": [{"ip": "172.16.0.10", "expired": False}],
        "ids_alerts": [{"src_ip": "172.16.0.50", "alert": "test"}],
        "interface_stats": [{"interface": "lan", "rx_errors": 0}],
    }

    result = lab_status_service.normalize_opnsense_payload(payload)

    assert result["gateway_down_count"] == 1
    assert result["dhcp"]["lease_count"] == 2
    assert result["dhcp"]["online_count"] == 1
    assert result["arp"]["entry_count"] == 1
    assert result["ids"]["alert_count"] == 1


def test_sensor_fleet_marks_missing_and_stale_collectors(app):
    now = datetime.utcnow()
    with app.app_context():
        active = SensorAgent(
            agent_id="active-agent",
            hostname="active",
            last_seen_at=now,
            tags=json.dumps(["category:endpoint"]),
        )
        stale = SensorAgent(
            agent_id="stale-agent",
            hostname="stale",
            last_seen_at=now - timedelta(minutes=10),
        )
        db.session.add_all([active, stale])
        db.session.add(SensorTelemetry(
            agent_id="active-agent",
            collected_at=now,
            collectors_json=json.dumps({"system": {"cpu_pct": 10}}),
        ))
        db.session.commit()

        rows = {"active-agent": SensorTelemetry.query.filter_by(agent_id="active-agent").first()}
        result = lab_status_service.normalize_sensor_fleet([active, stale], rows, now=now)

    assert result["active"] == 1
    assert result["stale"] == 1
    assert result["collector_coverage"]["system"] == 1
    assert result["agents"][1]["latest_collected_at"] is None


def test_attention_scoring_prioritizes_expected_signals():
    attention = lab_status_service.build_attention(
        reachability={
            "loopbacks": {"items": [{"name": "Gateway", "status": "down"}]},
            "services": {"items": []},
            "infrastructure": {"items": []},
        },
        sensor_fleet={"agents": [{"agent_id": "node-1", "status": "offline"}]},
        network={"opnsense": {"gateway_down_count": 0, "ids": {"alert_count": 1, "alerts": [{"sid": 1}]}}},
        dns={"lab": {"summary": {"percent_blocked": 42}}, "home": {"summary": {"percent_blocked": 5}}},
        flows={"flagged_hosts": [{"ip": "172.16.0.9", "score": 90}]},
        infrastructure={"proxmox": {"nodes": []}},
    )

    titles = [item["title"] for item in attention]
    assert "Gateway is down" in titles
    assert "node-1 sensor is offline" in titles
    assert any("IDS alert" in title for title in titles)
    assert any("block rate is high" in title for title in titles)
    assert any("High ntopng flow score" in title for title in titles)


def test_build_overview_with_seeded_telemetry(app):
    now = datetime.utcnow()
    snapshot = {
        "overall_status": "healthy",
        "health_percentage": 100.0,
        "total_items": 1,
        "up_items": 1,
        "down_items": 0,
        "timestamp": now.isoformat(),
        "last_update": now.isoformat(),
        "categories": {
            "loopbacks": {"total": 0, "up": 0, "items": []},
            "services": {"total": 0, "up": 0, "items": []},
            "infrastructure": {"total": 1, "up": 1, "items": [{"name": "OPNsense", "status": "up"}]},
        },
    }

    with app.app_context():
        agents = [
            SensorAgent(agent_id="opnsense", hostname="opnsense", last_seen_at=now, role="network-sensor"),
            SensorAgent(agent_id="opnsense-ntopng", hostname="ntopng", last_seen_at=now, role="network-sensor"),
            SensorAgent(agent_id="pihole-lab", hostname="pihole-lab", last_seen_at=now, role="network-sensor"),
            SensorAgent(agent_id="proxmox-1", hostname="pmx", last_seen_at=now, role="proxmox-node"),
        ]
        db.session.add_all(agents)
        db.session.add_all([
            SensorTelemetry(
                agent_id="opnsense",
                collected_at=now,
                collectors_json=json.dumps({"ids_alerts": [{"sid": 1}], "dhcp_leases": [{"status": "online"}]}),
            ),
            SensorTelemetry(
                agent_id="opnsense-ntopng",
                collected_at=now,
                collectors_json=json.dumps({"active_hosts": {"total_active": 2, "flagged": [{"ip": "172.16.0.9", "score": 55}]}}),
            ),
            SensorTelemetry(
                agent_id="pihole-lab",
                collected_at=now,
                collectors_json=json.dumps({"summary": {"total": 100, "blocked": 40, "percent_blocked": 40}}),
            ),
            SensorTelemetry(
                agent_id="proxmox-1",
                collected_at=now,
                collectors_json=json.dumps({"proxmox": {"node": "pmx", "node_status": "online", "guest_count": 3, "running_guests": 2}}),
            ),
        ])
        db.session.commit()

        with patch("src.services.lab_status_service.get_summary_data", return_value=snapshot):
            overview = lab_status_service.build_overview(window_minutes=120, use_cache=False)

    assert overview["summary"]["window_minutes"] == 120
    assert overview["network"]["inventory"]["dhcp_lease_count"] == 1
    assert overview["flows"]["active_host_count"] == 2
    assert overview["dns"]["lab"]["summary"]["percent_blocked"] == 40
    assert overview["infrastructure"]["proxmox"]["guest_count"] == 3
    assert len(overview["attention"]) <= 20
