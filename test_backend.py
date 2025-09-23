#!/usr/bin/env python3
"""
Simple test to check if the backend can start
"""
import sys
import os

# Add the backend directory to the path
sys.path.insert(0, '/home/sentinel/SentinelZero/backend')

try:
    print("Testing backend imports...")
    from src.services.whats_up import INFRASTRUCTURE
    print(f"✅ INFRASTRUCTURE loaded with {len(INFRASTRUCTURE)} items")
    
    from src.routes.whatsup_routes import bp
    print("✅ Whatsup routes loaded")
    
    from app import app
    print("✅ Flask app created")
    
    print("✅ All imports successful - backend should work")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
