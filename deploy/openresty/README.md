# OpenResty gateway config for `ai.itrecruitment.dpdns.org`

This folder contains the production-like reverse proxy config for exposing the AI service without ngrok.

Cloudflare should stay in `Proxied` mode and SSL/TLS mode should be set to `Full (strict)`.

## Files

- `00-websocket-map.conf`: shared `map` block for websocket upgrade headers.
- `ai.itrecruitment.dpdns.org.conf`: vhost that redirects HTTP to HTTPS and proxies to `172.16.64.68:8080`.
- `install_gateway.sh`: safe install helper for the public OpenResty gateway.
- `verify_public.sh`: end-to-end check for the public domain after reload.

## Target install path on the gateway

Prefer:

- `/etc/openresty/conf.d/00-websocket-map.conf`
- `/etc/openresty/conf.d/ai.itrecruitment.dpdns.org.conf`

If `openresty -T` shows a source install include path, use:

- `/usr/local/openresty/nginx/conf/conf.d/00-websocket-map.conf`
- `/usr/local/openresty/nginx/conf/conf.d/ai.itrecruitment.dpdns.org.conf`

## Safe deployment order

```bash
sudo openresty -T 2>&1 | rg -n "server_name|listen 80|listen 443|default_server|conf.d|sites-enabled"
sudo ss -tulpn | rg ":80|:443"
curl http://172.16.64.68:8080/health
```

```bash
sudo mkdir -p /root/backup-openresty-$(date +%F-%H%M)
sudo cp -a /etc/openresty /root/backup-openresty-$(date +%F-%H%M)/ 2>/dev/null || true
sudo cp -a /usr/local/openresty/nginx/conf /root/backup-openresty-$(date +%F-%H%M)/ 2>/dev/null || true
```

```bash
sudo mkdir -p /etc/ssl/cloudflare
sudo chmod 700 /etc/ssl/cloudflare
sudo tee /etc/ssl/cloudflare/itrecruitment-origin.crt >/dev/null
sudo tee /etc/ssl/cloudflare/itrecruitment-origin.key >/dev/null
sudo chmod 600 /etc/ssl/cloudflare/itrecruitment-origin.key
```

Copy the two config files into the include directory, then validate and reload:

```bash
sudo openresty -t
sudo systemctl reload openresty
```

If the gateway does not use `systemd`:

```bash
sudo openresty -s reload
```

Or run the helper directly on the gateway after the Cloudflare origin cert and key are in place:

```bash
cd deploy/openresty
sudo ./install_gateway.sh
```

The installer now verifies that the upstream backend answers on `http://172.16.64.68:8080/health` before it touches the gateway config.

## Rollback

```bash
sudo mv /etc/openresty/conf.d/ai.itrecruitment.dpdns.org.conf /etc/openresty/conf.d/ai.itrecruitment.dpdns.org.conf.disabled
sudo openresty -t
sudo systemctl reload openresty
```

Adjust the path if the gateway uses `/usr/local/openresty/nginx/conf/conf.d/`.

## End-to-end test

```bash
./verify_public.sh
```

Expected:

- `http://ai...` returns `301` to HTTPS
- `https://ai.../health` returns `200`
- `https://ai.../docs` returns `200`
- `https://ai.../` is served by the backend, not the OpenResty default `404`
