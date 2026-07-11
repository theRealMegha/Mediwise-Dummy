#!/usr/bin/env bash

# Exit on error
set -o errexit

# Install dependencies
pip install -r requirements.txt

# Convert static assets to be served by WhiteNoise
python manage.py collectstatic --no-input

# Apply database migrations to Neon (PostgreSQL)
python manage.py migrate