#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Runner script for the Emsys application.

This script sets up the Python path correctly and runs the application,
ensuring that imports work properly.
"""

import os
import sys

# Add the project root directory to the Python path 
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Run the main application
from emsys.main import main

if __name__ == "__main__":
    main()