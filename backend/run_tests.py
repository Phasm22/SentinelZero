#!/usr/bin/env python3
"""
Comprehensive test runner for SentinelZero backend
Runs all tests and provides detailed reporting
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path

def run_command(cmd, description):
    """Run a command and return success status"""
    print(f"\n{'='*60}")
    print(f"🧪 {description}")
    print(f"{'='*60}")
    print(f"Running: {cmd}")
    print()
    
    try:
        result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Command failed with exit code {e.returncode}")
        print("STDOUT:", e.stdout)
        print("STDERR:", e.stderr)
        return False

def main():
    parser = argparse.ArgumentParser(description='Run SentinelZero backend tests')
    parser.add_argument('--unit', action='store_true', help='Run unit tests only')
    parser.add_argument('--integration', action='store_true', help='Run integration tests only')
    parser.add_argument('--coverage', action='store_true', help='Run with coverage report')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    parser.add_argument('--file', help='Run specific test file')
    
    args = parser.parse_args()
    
    # Change to backend directory
    backend_dir = Path(__file__).parent
    os.chdir(backend_dir)
    
    print("🛡️  SentinelZero Backend Test Suite")
    print("="*60)
    
    # Base pytest command
    base_cmd = "python -m pytest"
    
    if args.verbose:
        base_cmd += " -v"
    
    if args.coverage:
        base_cmd += " --cov=src --cov-report=html --cov-report=term"
    
    # Determine which tests to run
    test_paths = []
    
    if args.unit:
        test_paths.append("tests/unit/")
    elif args.integration:
        test_paths.append("tests/integration/")
    elif args.file:
        test_paths.append(args.file)
    else:
        # Run all tests
        test_paths.extend(["tests/unit/", "tests/integration/"])
    
    # Run tests
    all_passed = True
    
    for test_path in test_paths:
        if os.path.exists(test_path):
            cmd = f"{base_cmd} {test_path}"
            if not run_command(cmd, f"Running tests in {test_path}"):
                all_passed = False
        else:
            print(f"⚠️  Test path {test_path} does not exist, skipping...")
    
    # Summary
    print(f"\n{'='*60}")
    if all_passed:
        print("✅ All tests passed!")
    else:
        print("❌ Some tests failed!")
    print(f"{'='*60}")
    
    # Show coverage report if requested
    if args.coverage and all_passed:
        print("\n📊 Coverage report generated in htmlcov/index.html")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
