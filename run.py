#!/usr/bin/env python3
"""
Entry point for the Gantt Project Management Tool.

Run this file to start the application.
"""

import sys
import os

# Add the current directory to Python path so we can import gantt_app
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gantt_app.main import main

if __name__ == "__main__":
    main()
