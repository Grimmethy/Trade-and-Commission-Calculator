# Putting the public trade calculator on the website

Service: `trade-calculator-public` (systemd user unit on grimm-linux, `~/trade-calculator`, 127.0.0.1:7463, branch `plugin`).
Update: `ssh grimm-linux 'cd ~/trade-calculator && git pull --ff-only && systemctl --user restart trade-calculator-public'`.

## 1. Move DNS from Namecheap to Cloudflare (registration stays at Namecheap)
Records that exist today (read from public DNS 2026-10-31). Check Namecheap > Advanced DNS for anything this list lacks before switching name servers.

| Type | Name | Value | Cloudflare proxy |
|---|---|---|---|
| A | @ | 199.34.228.184 (Square) | DNS only (grey cloud) |
| CNAME | www | screaminggoatcollectibles.com | DNS only |
| MX | @ | mx.zoho.com (10), mx3.zoho.com (10), mx2.zoho.com (20) | n/a |
| TXT | @ | v=spf1 include:zoho.com ~all | n/a |
| TXT | @ | zoho-verification=zb97718434.zmverify.zoho.com | n/a |
| TXT | @ | 83ac67c0-0ba3-11f1-87a0-210a6fab9ff4 | n/a |
| TXT | @ | pinterest-site-verification=ee019811fd8bc201cab2d3c9cf168e60 | n/a |
| TXT | zmail._domainkey | v=DKIM1;k=rsa;p=MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQCm0h1WSYGGtnHTV6f3lfdVcmOuCXZuBFTbB4QRmy2VMcVC1zadAy3MV92ypXuJBxHBkfOi9cRAVvpjbjhQWHdTXBzSqOtJ9VULsfkL2xBKnJz1oQbNN4VbHm2ObK0i0vOedQOqBgjtdoowfMgFm6YVUi7BQX7QC1G2cDTwwX/WuwIDAQAB | n/a |

Keep the Square records unproxied so Square can keep issuing its certificate.

## 2. Tunnel
In the same Cloudflare account as the zone: Zero Trust > Networks > Tunnels > create tunnel, install the connector token on grimm-linux as a second `cloudflared` service (the PF tunnel stays as it is), public hostname `trade.screaminggoatcollectibles.com` -> http://localhost:7463.

## 3. Square site
Add a nav link or an Embed code block pointing at https://trade.screaminggoatcollectibles.com (editing and publishing in Square is the owner's step).

## 4. Check after switching
Site, email send and receive, and https://trade.screaminggoatcollectibles.com/healthz returning {"ok":true,"mode":"public"}.
