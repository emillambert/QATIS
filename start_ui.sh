#!/bin/bash
# QATIS UI Launcher
# Usage: ./start_ui.sh

cd "$(dirname "$0")"

# Activate virtual environment
source .qatis-ui/bin/activate

# Ensure qatis package is installed in editable mode
pip install -e . --quiet

# Launch Streamlit UI
streamlit run qatis/ui_app.py


