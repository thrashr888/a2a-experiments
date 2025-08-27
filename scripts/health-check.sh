#!/bin/bash

# Health check script for the A2A application
# This script checks if the application is responding properly

set -e

# Check if the main web server is responding
if curl -f -s http://localhost:8080/health > /dev/null 2>&1; then
    echo "Health check passed: Web server is responding"
    exit 0
else
    echo "Health check failed: Web server is not responding"
    exit 1
fi