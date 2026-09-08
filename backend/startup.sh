#!/usr/bin/env bash
# Azure App Service startup command.
# Run as: bash startup.sh
set -euo pipefail

python manage.py migrate --noinput
exec python -m daphne -b 0.0.0.0 -p 8000 config.asgi:application
