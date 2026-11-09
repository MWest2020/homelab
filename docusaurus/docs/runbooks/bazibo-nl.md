---
title: bazibo.nl (site and mail)
sidebar_position: 12
---

# bazibo.nl: website and mail

Bazibo is Mark's children's game app (repo `MWest2020/bazibo`). Since 2026-11-09 it has its
own domain. Nothing here runs on the homelab cluster; this page says where it does run.

## What lives where

| Part | Where | Notes |
|---|---|---|
| Domain | registrar Realtime Register, reseller **Yourhosting** | bought by Mark on 2026-11-09 |
| DNS | Yourhosting **Premium DNS** (`ns50.premiumdns-yourhosting.net`, `ns110…nl`, `ns92…eu`) | edited in *Mijn Yourhosting*, not in Plesk |
| Hosting | Yourhosting Plesk "Basic (Web + Mail)", server `web-1066.yourhosting.nl` (92.63.174.175) | panel `https://web-1066.yourhosting.nl:8443/` |
| Site files | Plesk Git repo `bazibo.git` → `/bazibo-repo` | document root `bazibo-repo/web`, so only `web/` is reachable |
| Deploy | GitHub webhook (push) on `MWest2020/bazibo` → Plesk pulls `main` and publishes automatically | hook id 709372838; deliveries visible with `gh api repos/MWest2020/bazibo/hooks/709372838/deliveries` |
| TLS | Let's Encrypt via Plesk **SSL It!**: `bazibo.nl`, `www.bazibo.nl`, `mail.bazibo.nl` | renews itself 30 days before expiry (first one valid to 2027-02-07) |
| Redirects | HTTP → HTTPS (301), `www` → `bazibo.nl` (301, "Voorkeursdomein") | Plesk hosting settings |
| Mail | MX `primary/fallback.yourfilter.nl` → Plesk; **hallo@bazibo.nl** is a forwarder (no mailbox) to mark@westerweel.work, with alias **hello@bazibo.nl** (Plesk: Mail → hallo@bazibo.nl → E-mailaliassen, added 2026-11-09) | tested 2026-11-09 |
| DKIM / DMARC | signing on in Plesk (selector `default`); `_dmarc` and `_domainkey` published 2026-11-09 | `default._domainkey` still to publish (below) |
| Second copy of the site | GitHub Pages `https://mwest2020.github.io/bazibo/` (CI in the repo) | independent of Yourhosting |

The provider's placeholder page is kept in `httpdocs/_yourhosting-default/` (no longer served).

## Credentials (OpenBao KV, values never in git)

| Path | What |
|---|---|
| `kv/westerweel/bazibo-ftp` | hosting system user: FTP(S) **and** the Plesk login |
| `kv/westerweel/bazibo-mail` | the `hallo@bazibo.nl` mail account (forwarder) |
| `kv/westerweel/soverin` | Mark's Soverin mailbox (IMAP), where the forwarded mail lands; read-only use |
| `kv/westerweel/yourhosting` | *Mijn Yourhosting* (registrar + Premium DNS): username, customer number, password |

Read one from jumpy the same way as in [key-backups](key-backups.md), e.g.
`bao kv get -field=username kv/westerweel/bazibo-ftp`. *Mijn Yourhosting* (DNS) is at
https://account.yourhosting.nl/ → Domeinnamen → bazibo.nl → DNS beheer → "Voeg record toe"
(type, name without `.bazibo.nl`, value without quotes, TTL, "Wijzigingen opslaan").

## Mail authentication records (Mijn Yourhosting → bazibo.nl → DNS)

Published 2026-11-09 (TTL 3600), checked with `dig TXT <name>.bazibo.nl @ns50.premiumdns-yourhosting.net`:

```
_dmarc.bazibo.nl.              TXT  "v=DMARC1; p=none; rua=mailto:hallo@bazibo.nl"
_domainkey.bazibo.nl.          TXT  "o=-"
```

Still to publish (the agent's save was refused by its safety check; Mark adds it by hand):

```
default._domainkey.bazibo.nl.  TXT  "v=DKIM1; p=<key shown in Plesk: Mail-instellingen › bazibo.nl › Het instellen van externe DNS>"
```

After adding it, check that the key in DNS equals the one in Plesk (join the quoted chunks
of the `dig` answer; DNS splits long TXT values into 255-character strings).

SPF is already right (`v=spf1 include:_spf.yourfilter.nl mx a ~all`; `a` covers the Plesk
server). Move DMARC to `p=quarantine` after about three weeks of clean aggregate reports (they arrive at hallo@bazibo.nl, so in Mark's mailbox); edit the `_dmarc` record in place.

## Checks

```sh
curl -sI https://bazibo.nl/ | head -1                        # 200
curl -sI http://www.bazibo.nl/ | grep -i location             # https://bazibo.nl/ (via one or two 301s)
echo | openssl s_client -connect bazibo.nl:443 -servername bazibo.nl 2>/dev/null \
  | openssl x509 -noout -enddate -ext subjectAltName          # LE, bazibo.nl/www/mail
curl -s https://bazibo.nl/.git/config -o /dev/null -w '%{http_code}\n'   # 403/404, never 200
```

## Roll back

- **Site:** in Plesk set the document root back to `httpdocs` (Hosting settings) and/or set
  the Git repo's deploy mode to *Handmatig*. The GitHub Pages copy keeps working regardless.
- **A bad deploy:** revert the commit on `main`; the webhook publishes the revert.
- **Mail:** delete or edit the forwarder under Mail › E-mailadressen.
- **TLS:** SSL It! › *Toewijzing certificaat opheffen*; re-issue with *Certificaat opnieuw uitgeven*.
