#!/bin/sh
set -eu

n8n import:workflow --input=/workflows/delivery-scan.json
n8n import:workflow --input=/workflows/abandoned-cart.json
n8n import:workflow --input=/workflows/outbox-dispatch.json

exec n8n start
