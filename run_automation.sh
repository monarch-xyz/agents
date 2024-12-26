#!/bin/bash

# Get the directory where the script is located
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Activate virtual environment
source "$DIR/venv/bin/activate"

# Change to project directory
cd "$DIR"

# Run the Python script
python main.py

# Deactivate virtual environment
deactivate
crontab -lcrontab -l