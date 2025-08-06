#!/bin/bash

echo "Setting up SentinelZero loopback sentinels using dummy0..."

# Ensure dummy module is loaded
sudo modprobe dummy
sudo ip link add dummy0 type dummy 2>/dev/null
sudo ip link set dummy0 up

# Assign /32 loopbacks
sudo ip addr add 172.16.0.254/32 dev dummy0 2>/dev/null || echo "172.16.0.254 already exists"
sudo ip addr add 192.168.68.254/32 dev dummy0 2>/dev/null || echo "192.168.68.254 already exists"

# Verify
echo "  LAN Sentinel (172.16.0.254):"
ping -c 1 -W 1 172.16.0.254 > /dev/null && echo "    ✅ UP" || echo "    ❌ DOWN"

echo "  VPN Sentinel (192.168.68.254):"
ping -c 1 -W 1 192.168.68.254 > /dev/null && echo "    ✅ UP" || echo "    ❌ DOWN"