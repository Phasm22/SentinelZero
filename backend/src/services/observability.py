"""Structured logging and correlation helpers."""
import json
import logging
import uuid
from datetime import datetime

from flask import g, has_request_context, request


LOGGER_NAME = 'sentinelzero'


def configure_logging():
    logger = logging.getLogger(LOGGER_NAME)
    if logger.handlers:
        return logger
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(message)s'))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger


def get_request_id():
    if has_request_context() and getattr(g, 'request_id', None):
        return g.request_id
    return None


def ensure_request_id():
    if not has_request_context():
        return None
    request_id = request.headers.get('X-Request-ID') or request.headers.get('X-Correlation-ID')
    if not request_id:
        request_id = str(uuid.uuid4())
    g.request_id = request_id
    return request_id


def log_event(event_name, level='info', **fields):
    logger = configure_logging()
    payload = {
        'event': event_name,
        'ts': datetime.utcnow().isoformat() + 'Z',
    }
    request_id = get_request_id()
    if request_id:
        payload['request_id'] = request_id
    if has_request_context():
        payload['path'] = request.path
        payload['method'] = request.method
    payload.update({k: v for k, v in fields.items() if v is not None})
    log_line = json.dumps(payload, separators=(',', ':'))
    getattr(logger, level, logger.info)(log_line)

