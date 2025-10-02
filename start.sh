#!/bin/bash

# Activate the python environment
source .venv/bin/activate

# Use DEBUG mode if you need
# In DEBUG mode, the logs will be displayed in the console, and will also be recorded to logs/cumulus_debug.log
# be aware that this log file will not be erased, and might eventually get really big with time
# The other difference in DEBUG mode is that old files and old jobs will not be cleaned
export CUMULUS_DEBUG="true"

# Start the server
python cumulus.py
