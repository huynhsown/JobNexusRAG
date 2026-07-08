#!/usr/bin/env bash
set -euo pipefail

DOMAIN="${1:-ai.itrecruitment.dpdns.org}"
HTTP_URL="http://${DOMAIN}/health"
HTTPS_URL="https://${DOMAIN}/health"
DOCS_URL="https://${DOMAIN}/docs"

echo "Checking ${HTTP_URL}"
curl -I --max-time 15 "${HTTP_URL}"
echo

echo "Checking ${HTTPS_URL}"
curl -I --max-time 15 "${HTTPS_URL}"
echo

echo "Checking ${HTTPS_URL} body"
curl --max-time 15 "${HTTPS_URL}"
echo

echo "Checking ${DOCS_URL}"
curl -I --max-time 15 "${DOCS_URL}"
