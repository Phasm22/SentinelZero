"""HTTP reporter — registers the agent and ships telemetry to SentinelZero."""
from __future__ import annotations
import logging
import time

import requests

log = logging.getLogger('sentinel-sensor')


class Reporter:
    def __init__(self, api_url: str, api_key: str, timeout: int = 10):
        self._url = api_url.rstrip('/')
        self._timeout = timeout
        self._session = requests.Session()
        if api_key:
            self._session.headers['X-Sensor-Key'] = api_key
        self._session.headers['Content-Type'] = 'application/json'
        self._identity: dict | None = None

    def register_agent(self, agent_id: str, hostname: str, host_ip: str,
                       role: str, version: str, tags: list | None = None) -> None:
        self._identity = {
            'agent_id': agent_id,
            'hostname': hostname,
            'host_ip': host_ip,
            'role': role,
            'agent_version': version,
            'tags': tags or [],
        }
        url = f'{self._url}/api/sensor/register'
        for attempt in range(5):
            try:
                resp = self._session.post(url, json=self._identity, timeout=self._timeout)
                resp.raise_for_status()
                log.info('[reporter] agent registered: %s', resp.json().get('status'))
                return
            except requests.RequestException as e:
                wait = min(2 ** attempt, 30)
                log.warning(
                    '[reporter] registration attempt %d/5 failed: %s — retry in %ds',
                    attempt + 1, e, wait,
                )
                if attempt < 4:
                    time.sleep(wait)
        log.warning('[reporter] registration failed — ingest may auto-register on next cycle')

    def post_telemetry(self, payload: dict, retries: int = 3) -> bool:
        if self._identity:
            payload = {**self._identity, **payload}
        url = f'{self._url}/api/sensor/ingest'
        for attempt in range(retries):
            try:
                resp = self._session.post(url, json=payload, timeout=self._timeout)
                if resp.status_code == 404 and self._identity:
                    log.warning('[reporter] ingest 404 — re-registering %s', payload.get('agent_id'))
                    self.register_agent(**{
                        'agent_id': self._identity['agent_id'],
                        'hostname': self._identity['hostname'],
                        'host_ip': self._identity['host_ip'],
                        'role': self._identity['role'],
                        'version': self._identity.get('agent_version', ''),
                        'tags': self._identity.get('tags', []),
                    })
                    continue
                resp.raise_for_status()
                return True
            except requests.RequestException as e:
                wait = 2 ** attempt
                log.warning(
                    '[reporter] POST attempt %d/%d failed: %s — retry in %ds',
                    attempt + 1, retries, e, wait,
                )
                if attempt < retries - 1:
                    time.sleep(wait)
        log.error('[reporter] all retries failed — telemetry dropped for this cycle')
        return False
