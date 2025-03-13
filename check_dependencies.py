#!/usr/bin/env python3
"""
Dependency checker script for The Digger application
Checks for outdated packages and generates a report
"""
import subprocess
import sys
import json
from datetime import datetime

def check_outdated_packages():
    """Check for outdated packages and return the results"""
    print("Checking for outdated packages...")
    try:
        # Run pip list --outdated --format=json
        result = subprocess.run(
            [sys.executable, "-m", "pip", "list", "--outdated", "--format=json"],
            capture_output=True,
            text=True,
            check=True
        )
        outdated = json.loads(result.stdout)
        return outdated
    except subprocess.CalledProcessError as e:
        print(f"Error checking packages: {e}")
        return []

def generate_report(outdated_packages):
    """Generate a report of outdated packages"""
    if not outdated_packages:
        print("All packages are up to date!")
        return
    
    print(f"\nFound {len(outdated_packages)} outdated package(s):")
    print("-" * 80)
    print(f"{'Package':<20} {'Current':<15} {'Latest':<15} {'Type':<10}")
    print("-" * 80)
    
    for pkg in outdated_packages:
        print(f"{pkg['name']:<20} {pkg['version']:<15} {pkg['latest_version']:<15} {pkg.get('latest_filetype', ''):<10}")
    
    print("\nTo update all packages, run:")
    print("pip install -r requirements.txt --upgrade")
    print("\nTo update requirements.txt with the latest versions:")
    print("pip freeze > requirements.txt")
    
    # Save report to file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"dependency_report_{timestamp}.txt"
    with open(filename, "w") as f:
        f.write(f"Dependency Report for The Digger - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Found {len(outdated_packages)} outdated package(s):\n")
        f.write("-" * 80 + "\n")
        f.write(f"{'Package':<20} {'Current':<15} {'Latest':<15} {'Type':<10}\n")
        f.write("-" * 80 + "\n")
        
        for pkg in outdated_packages:
            f.write(f"{pkg['name']:<20} {pkg['version']:<15} {pkg['latest_version']:<15} {pkg.get('latest_filetype', ''):<10}\n")
    
    print(f"\nReport saved to {filename}")

if __name__ == "__main__":
    print(f"Dependency checker for The Digger - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    outdated = check_outdated_packages()
    generate_report(outdated) 