#!/bin/bash
# Build script for Vercel Deployment
echo "Installing project dependencies..."
python3.12 -m pip install -r requirements.txt

echo "Collecting static assets with WhiteNoise..."
python3.12 manage.py collectstatic --noinput --clear
