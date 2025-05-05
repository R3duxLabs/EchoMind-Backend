#!/usr/bin/env bash
# This script is executed by Render during the build process

echo "Installing dependencies..."
pip install -r requirements.txt

echo "Build completed successfully!"
exit 0