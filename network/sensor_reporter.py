"""Shared HTTP reporter for SentinelZero network sensors."""
from __future__ import annotations

import logging
import time
from typing import Any, Optional

import requests

log = logging.getLogger('sentinel-sensor-reporter')


class Reporter:
    """Register + ingest with auto re-register on backend DB reset."""

    def __init__(self, api_url: str, api_key: str, timeout: int = 10):
        self._url = api_url.rstrip('/')
        self._timeout = timeout
        self._session = requests.Session()
        if api_key:
            self._session.headers['X-Sensor-Key'] = api_key
        self._session.headers['Content-Type'] = 'application/json'
        self._identity: Optional[dict[str, Any]] = None

    def register(
        self,
        agent_id: str,
        hostname: str,
        host_ip: str,
        role: str,
        tags: list,
        *,
        version: str = '',
        retries: int = 5,
    ) -> bool:
        self._identity = {
            'agent_id': agent_id,
            'hostname': hostname,
            'host_ip': host_ip,
            'role': role,
            'tags': tags,
            'agent_version': version,
        }
        payload = dict(self._identity)
        for attempt in range(retries):
            try:
                r = self._session.post(
                    f'{self._url}/api/sensor/register',
                    json=payload,
                    timeout=self._timeout,
                )
                r.raise_for_status()
                log.info('[reporter] registered: %s', r.json().get('status'))
                return True
            except requests.RequestException as e:
                wait = min(2 ** attempt, 30)
                log.warning(
                    '[reporter] registration attempt %d/%d failed: %s — retry in %ds',
                    attempt + 1, retries, e, wait,
                )
                if attempt < retries - 1:
                    time.sleep(wait)
        log.warning('[reporter] registration exhausted retries — ingest may auto-register')
        return False

    def ingest(self, payload: dict, retries: int = 3) -> bool:
        if self._identity:
            payload = {**self._identity, **payload}

        for attempt in range(retries):
            try:
                r = self._session.post(
                    f'{self._url}/api/sensor/ingest',
                    json=payload,
                    timeout=self._timeout,
                )
                if r.status_code == 404:
                    log.warning('[reporter] ingest 404 — re-registering %s', payload.get('agent_id'))
                    if self._identity:
                        self.register(**{
                            k: self._identity[k]
                            for k in ('agent_id', 'hostname', 'host_ip', 'role', 'tags')
                        }, version=self._identity.get('agent_version', ''), retries=2)
                    continue
                r.raise_for_status()
                return True
            except requests.RequestException as e:
                wait = 2 ** attempt
                log.warning(
                    '[reporter] attempt %d/%d failed: %s — retry in %ds',
                    attempt + 1, retries, e, wait,
                )
                if attempt < retries - 1:
                    time.sleep(wait)
        log.error('[reporter] all retries failed — telemetry dropped')
        return False

    def maybe_reregister(self, cycle: int, every: int = 10) -> None:
        """Periodic idempotent register so tags/metadata stay fresh."""
        if self._identity and cycle > 1 and cycle % every == 0:
            self.register(
                self._identity['agent_id'],
                self._identity['hostname'],
                self._identity['host_ip'],
                self._identity['role'],
                self._identity['tags'],
                version=self._identity.get('agent_version', ''),
                retries=2,
            )
