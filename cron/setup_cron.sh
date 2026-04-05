#!/bin/bash
# Installation crontab pour DiffusionBot
# Usage: bash cron/setup_cron.sh

PYTHON="$(pwd)/.venv/bin/python"
PROJECT="$(pwd)"

echo "Configuration crontab DiffusionBot..."

# Generer les lignes cron
CRON_LINES=$(cat <<EOF
# === DiffusionBot ===
# Worker Diffusion: 3 fois par jour
0 9 * * * cd $PROJECT && $PYTHON -m cron.entrypoints diffusion >> logs/diffusion.log 2>&1
0 13 * * * cd $PROJECT && $PYTHON -m cron.entrypoints diffusion >> logs/diffusion.log 2>&1
0 17 * * * cd $PROJECT && $PYTHON -m cron.entrypoints diffusion >> logs/diffusion.log 2>&1

# Worker Monitoring: chaque lundi a 3h
0 3 * * 1 cd $PROJECT && $PYTHON -m cron.entrypoints monitoring >> logs/monitoring.log 2>&1

# Worker Analytics: chaque mercredi a 4h
0 4 * * 3 cd $PROJECT && $PYTHON -m cron.entrypoints analytics >> logs/analytics.log 2>&1

# Worker Intelligence: 1er du mois a 2h
0 2 1 * * cd $PROJECT && $PYTHON -m cron.entrypoints intelligence >> logs/intelligence.log 2>&1
EOF
)

# Ajouter au crontab existant (sans doublons)
(crontab -l 2>/dev/null | grep -v "DiffusionBot" | grep -v "cron.entrypoints"; echo "$CRON_LINES") | crontab -

echo "Crontab mis a jour. Verification:"
crontab -l | grep -A 20 "DiffusionBot"
