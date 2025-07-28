"""
Database models for SentinelZero
"""
from .scan import Scan
from .alert import Alert

__all__ = ['Scan', 'Alert']
