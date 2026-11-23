"""Unit tests for schedule_service migration and hunter_timers."""
from unittest.mock import patch

from src.services import hunter_timers, schedule_service


def test_migrate_legacy_disabled_object():
    assert schedule_service.migrate_legacy_settings({
        'enabled': False,
        'frequency': 'daily',
        'time': '03:00',
        'scan_type': 'Full TCP',
        'target_network': '172.16.0.0/22',
    }) == []


def test_migrate_legacy_enabled_object():
    jobs = schedule_service.migrate_legacy_settings({
        'enabled': True,
        'frequency': 'daily',
        'time': '03:30',
        'scanType': 'IoT Scan',
        'targetNetwork': '192.168.68.0/22',
    })

    assert len(jobs) == 1
    assert jobs[0]['enabled'] is True
    assert jobs[0]['scanType'] == 'IoT Scan'
    assert jobs[0]['hour'] == '3'
    assert jobs[0]['minute'] == '30'
    assert jobs[0]['targetNetwork'] == '192.168.68.0/22'


def test_migrate_array_passthrough():
    jobs = schedule_service.migrate_legacy_settings([{
        'enabled': True,
        'scanType': 'Discovery Scan',
        'minute': '15',
        'hour': '4',
        'day': '*',
        'month': '*',
        'dayOfWeek': '*',
        'targetNetwork': '172.16.0.0/22',
    }])

    assert len(jobs) == 1
    assert jobs[0]['scanType'] == 'Discovery Scan'
    assert jobs[0]['minute'] == '15'


def test_save_and_load_roundtrip(tmp_path, monkeypatch):
    path = tmp_path / 'scheduled_scans_settings.json'
    monkeypatch.setattr(schedule_service, 'SCHEDULE_SETTINGS_FILE', str(path))

    saved = schedule_service.save_scheduled_jobs([{
        'enabled': True,
        'scanType': 'Full TCP',
        'minute': '0',
        'hour': '2',
        'day': '*',
        'month': '*',
        'dayOfWeek': '*',
        'targetNetwork': '172.16.0.0/22',
    }])

    assert path.exists()
    loaded = schedule_service.load_scheduled_jobs()
    assert loaded[0]['scanType'] == saved[0]['scanType']
    assert loaded[0]['enabled'] is True


def test_hunter_timers_list_mocked():
    def fake_run(args, timeout=15):
        if args[0] == 'is-active':
            return 0, 'active', ''
        if args[0] == 'is-enabled':
            return 0, 'enabled', ''
        if args[0] == 'show':
            return 0, 'ActiveState=active\nUnitFileState=enabled\nNextElapseUSecRealtime=n/a\n', ''
        return 0, '', ''

    with patch.object(hunter_timers, '_run_systemctl', side_effect=fake_run), \
            patch.object(hunter_timers, '_find_unit_file', return_value=None):
        timers = hunter_timers.list_timers()

    assert len(timers) == 3
    assert timers[0]['name'] == 'lab_inventory'
    assert timers[0]['active'] is True
    assert timers[0]['enabled'] is True


def test_hunter_timer_patch_enable():
    with patch.object(hunter_timers, '_run_systemctl', return_value=(0, '', '')), \
            patch.object(hunter_timers, 'get_timer_status', return_value={'name': 'lab_inventory', 'enabled': True}):
        result = hunter_timers.patch_timer('lab_inventory', {'enabled': True})

    assert result['status'] == 'success'


def test_hunter_timer_unknown():
    result = hunter_timers.patch_timer('nope', {'enabled': True})
    assert result['status'] == 'error'
