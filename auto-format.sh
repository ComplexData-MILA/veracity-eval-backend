#!/bin/bash
echo "Auto-formatting Python code..."
black .
echo "Linting Python code..."
flake8 .