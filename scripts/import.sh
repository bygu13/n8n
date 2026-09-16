#!/usr/bin/env sh
# Imports the four workflows into a self-hosted n8n instance using the n8n CLI.
# The CLI keeps the workflow ids from the JSON files, so the tool nodes in the
# main workflow already point at the right sub-workflows.
#
# Usage (on the machine/container running n8n):
#   sh scripts/import.sh
# or with Docker:
#   docker cp workflows <container>:/tmp/workflows
#   docker exec -it <container> n8n import:workflow --separate --input=/tmp/workflows
set -eu
DIR="$(cd "$(dirname "$0")/.." && pwd)/workflows"
n8n import:workflow --separate --input="$DIR"
echo "Imported. Open n8n, set the Config nodes, attach credentials, then activate 'Dainuie – Telegram Social Media Manager'."
