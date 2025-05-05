#!/bin/bash
# Script to install dependencies even if Poetry fails

# First try Poetry
echo "Attempting to install with Poetry..."
poetry install || {
    echo "Poetry installation failed, falling back to pip..."
    
    # If Poetry fails, use pip directly
    pip install -r requirements.txt
    
    echo "Dependencies installed with pip"
    exit 0
}

echo "Dependencies installed with Poetry"
exit 0