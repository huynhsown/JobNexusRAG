#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OPENRESTY_BIN="${OPENRESTY_BIN:-$(command -v openresty || true)}"
CERT_PATH="${CERT_PATH:-/etc/ssl/cloudflare/itrecruitment-origin.crt}"
KEY_PATH="${KEY_PATH:-/etc/ssl/cloudflare/itrecruitment-origin.key}"
UPSTREAM_HEALTH_URL="${UPSTREAM_HEALTH_URL:-http://172.16.64.68:8080/health}"

if [[ -z "${OPENRESTY_BIN}" ]]; then
  echo "ERROR: openresty binary not found in PATH."
  exit 1
fi

CONF_DIR="${CONF_DIR:-}"
if [[ -z "${CONF_DIR}" ]]; then
  if [[ -d /etc/openresty/conf.d ]]; then
    CONF_DIR="/etc/openresty/conf.d"
  elif [[ -d /usr/local/openresty/nginx/conf/conf.d ]]; then
    CONF_DIR="/usr/local/openresty/nginx/conf/conf.d"
  else
    echo "ERROR: Could not detect OpenResty conf.d include directory."
    exit 1
  fi
fi

if [[ ! -f "${CERT_PATH}" ]]; then
  echo "ERROR: Missing Cloudflare origin cert at ${CERT_PATH}"
  exit 1
fi

if [[ ! -f "${KEY_PATH}" ]]; then
  echo "ERROR: Missing Cloudflare origin key at ${KEY_PATH}"
  exit 1
fi

backup_dir="/root/backup-openresty-$(date +%F-%H%M%S)"
echo "Using OpenResty binary: ${OPENRESTY_BIN}"
echo "Using config directory: ${CONF_DIR}"
echo "Creating backup at: ${backup_dir}"
echo "Checking upstream health: ${UPSTREAM_HEALTH_URL}"

if ! curl --fail --silent --show-error --max-time 10 "${UPSTREAM_HEALTH_URL}" >/dev/null; then
  echo "ERROR: Upstream backend health check failed at ${UPSTREAM_HEALTH_URL}"
  exit 1
fi

mkdir -p "${backup_dir}"
cp -a /etc/openresty "${backup_dir}/" 2>/dev/null || true
cp -a /usr/local/openresty/nginx/conf "${backup_dir}/" 2>/dev/null || true

install -m 0644 "${SCRIPT_DIR}/00-websocket-map.conf" "${CONF_DIR}/00-websocket-map.conf"
install -m 0644 "${SCRIPT_DIR}/ai.itrecruitment.dpdns.org.conf" "${CONF_DIR}/ai.itrecruitment.dpdns.org.conf"

echo "Validating OpenResty config..."
"${OPENRESTY_BIN}" -t

if systemctl list-unit-files openresty.service >/dev/null 2>&1; then
  echo "Reloading via systemd..."
  systemctl reload openresty
else
  echo "Reloading via openresty -s reload..."
  "${OPENRESTY_BIN}" -s reload
fi

echo "Deployment complete."
echo "Next checks:"
echo "  curl -I http://ai.itrecruitment.dpdns.org"
echo "  curl -I https://ai.itrecruitment.dpdns.org/health"
