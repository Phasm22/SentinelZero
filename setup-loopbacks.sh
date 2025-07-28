#!/bin/bash
# SentinelZero Loopback Setup Script
# Sets up loopback/sentinel IPs on network interfaces for health monitoring

echo "Setting up SentinelZero loopback sentinels..."

# Add loopback IPs to interfaces
echo "Adding 172.16.0.254 to eth0..."
ip addr add 172.16.0.254/22 dev eth0 2>/dev/null || echo "172.16.0.254 already exists on eth0"

echo "Adding 192.168.68.254 to eth1..."
ip addr add 192.168.68.254/22 dev eth1 2>/dev/null || echo "192.168.68.254 already exists on eth1"

# Verify the setup
echo "Verifying loopback setup:"
echo "  LAN Sentinel (172.16.0.254):"
ping -c 1 -W 1 172.16.0.254 > /dev/null && echo "    ✅ UP" || echo "    ❌ DOWN"

echo "  VPN Sentinel (192.168.68.254):"
ping -c 1 -W 1 192.168.68.254 > /dev/null && echo "    ✅ UP" || echo "    ❌ DOWN"

echo "Loopback sentinel setup complete!"
echo "Use these in SentinelZero What's Up monitoring."
