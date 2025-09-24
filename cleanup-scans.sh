#!/bin/bash

# SentinelZero Scan Cleanup Script
# Kills orphaned nmap processes and cancels running scans

echo "🧹 Cleaning up orphaned scans and processes..."

# Kill any nmap processes
echo "🔍 Checking for nmap processes..."
NMAP_COUNT=$(pgrep -f nmap | wc -l)
if [ $NMAP_COUNT -gt 0 ]; then
    echo "⚠️  Found $NMAP_COUNT nmap processes, killing them..."
    pkill -f nmap
    sleep 2
    echo "✅ Nmap processes killed"
else
    echo "✅ No nmap processes found"
fi

# Cancel running scans via API
echo "🔍 Checking for running scans..."
if curl -s http://localhost:5000/api/ping > /dev/null; then
    ACTIVE_SCANS=$(curl -s http://localhost:5000/api/active-scans | jq -r '.count' 2>/dev/null || echo "0")
    if [ "$ACTIVE_SCANS" -gt 0 ]; then
        echo "⚠️  Found $ACTIVE_SCANS active scans, cancelling them..."
        curl -s -X POST http://localhost:5000/api/kill-all-scans > /dev/null
        echo "✅ Active scans cancelled"
    else
        echo "✅ No active scans found"
    fi
else
    echo "⚠️  Backend not running, skipping scan cancellation"
fi

echo "🎉 Cleanup completed!"
