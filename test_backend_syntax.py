#!/usr/bin/env python3
"""
Test backend syntax
"""
import sys
import os

# Add the backend directory to the path
sys.path.insert(0, '/home/sentinel/SentinelZero/backend')

try:
    print("Testing backend syntax...")
    
    # Test the whatsup service
    from src.services.whats_up import get_loopbacks_data, get_services_data, get_infrastructure_data
    print("✅ All imports successful")
    
    # Test the functions
    print("Testing get_loopbacks_data...")
    loopbacks = get_loopbacks_data()
    print(f"✅ Loopbacks: {len(loopbacks)} items")
    
    print("Testing get_services_data...")
    services = get_services_data()
    print(f"✅ Services: {len(services)} items")
    
    print("Testing get_infrastructure_data...")
    infrastructure = get_infrastructure_data()
    print(f"✅ Infrastructure: {len(infrastructure)} items")
    
    print("✅ All tests passed!")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
