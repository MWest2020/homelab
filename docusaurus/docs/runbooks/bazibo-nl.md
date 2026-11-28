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
| Mail | MX `primary/fallback.yourfilter.nl` → Plesk; **hallo@bazibo.nl** is a mailbox (1 GB, since 2026-11-28) that also forwards to mark@westerweel.work, with alias **hello@bazibo.nl** (Plesk: Mail → hallo@bazibo.nl → E-mailaliassen, added 2026-11-09) | tested 2026-11-09 |
| DKIM / DMARC | signing on in Plesk (selector `default`); `_dmarc`, `_domainkey` and `default._domainkey` published | `default._domainkey` seen in DNS on 2026-11-27 (below) |
| Code mails (netnl) | the netnl facade mails Bazibo unlock codes as `hallo@bazibo.nl` via `mail.yourhosting.nl:465` (since 2026-11-28) | [below](#bazibo-code-mail-from-netnl) |
| Second copy of the site | GitHub Pages `https://mwest2020.github.io/bazibo/` (CI in the repo) | independent of Yourhosting |

The provider's placeholder page is kept in `httpdocs/_yourhosting-default/` (no longer served).

## Credentials (OpenBao KV, values never in git)

| Path | What |
|---|---|
| `kv/westerweel/bazibo-ftp` | hosting system user: FTP(S) **and** the Plesk login |
| `kv/westerweel/bazibo-mail` | the `hallo@bazibo.nl` mail account (forwarder; fields `address`, `password`). A forwarder without a mailbox cannot log in over SMTP in Plesk (below) |
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

Also in DNS (seen on 2026-11-27, on the public resolvers and on `ns50`):

```
default._domainkey.bazibo.nl.  TXT  "v=DKIM1; p=MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA7FSQ…IDAQAB;"
```

The key parses as an RSA-2048 public key. The value has runs of spaces inside the base64
(`…a0B   QVI3…`, `…Vlu   BWDII…`), most likely from copying it out of Plesk. RFC 6376 allows
whitespace in `p=` and verifiers strip it, so it should verify. Checked on 2026-11-28: it
equals the key in Plesk (Mail-instellingen › bazibo.nl › Het instellen van externe DNS), and a
test mail got `dkim=pass header.d=bazibo.nl`. To check again after a key change: Join the quoted chunks of the
`dig` answer and drop the spaces before you compare; DNS splits long TXT values into
255-character strings. If they differ, replace the record in *Mijn Yourhosting*
(Domeinnamen → bazibo.nl → DNS beheer: edit the `default._domainkey` TXT record, paste the Plesk
value without quotes or spaces, "Wijzigingen opslaan").

SPF is already right (`v=spf1 include:_spf.yourfilter.nl mx a ~all`; `a` covers the Plesk
server). Move DMARC to `p=quarantine` after about three weeks of clean aggregate reports (they arrive at hallo@bazibo.nl, so in Mark's mailbox); edit the `_dmarc` record in place.

## Bazibo code mail from netnl

The netnl facade (homelab `cluster-config/infra/netnl`, code in `MWest2020/internetnl-cli`,
OpenSpec `add-bazibo-mail-identity`) mails the unlock code to the buyer. Mark, 27 Nov 2026:
those mails must come from **hallo@bazibo.nl**. Only the code mail uses this identity. The
netnl supporter-key mail, the operator notification and the watch alert stay on the bridge's
`NETNL_SMTP_*` (Soverin, mark@westerweel.work).

### Now: mail.yourhosting.nl:465, From `Bazibo <hallo@bazibo.nl>` (since 2026-11-28)

- `NETNL_BAZIBO_SMTP_HOST=mail.yourhosting.nl`, port 465, mode `ssl` (implicit TLS), login
  and From `hallo@bazibo.nl` (password from OpenBao `kv/westerweel/bazibo-mail`), all in the
  Secret `netnl-bridge`, written by `scripts/switch-bazibo-smtp.sh`.
- `mail.yourhosting.nl` is the outgoing server Plesk itself names for the address (Mail →
  E-mailadressen → *Instellingen mailprogramma*). It is Yourhosting's mail proxy
  (`mail-yourhosting.prx.route25.eu`, 109.106.178.x / 109.106.179.x), **not** web-1066.
- **Not `mail.bazibo.nl:587`.** That name points at web-1066 (92.63.174.175), which rejects
  465/587/993 from outside (ICMP "prohibited", seen on 2026-11-28 from a GitHub runner and
  over IPv6 from agent-lxc). The first design aimed there and could never have worked.
- Test on 2026-11-28 (ref `test-hallo-20261128`, revoked afterwards): delivered via
  `se17-yh.route25.eu`, `From: Bazibo <hallo@bazibo.nl>`, `Reply-To: hallo@bazibo.nl`,
  `dkim=pass header.d=bazibo.nl`, `spf=pass`, `dmarc=pass`.
- The mailbox keeps a copy of every forwarded mail (forwarding stays on), so empty it now
  and then via webmail; 1 GB is plenty for years of code mails and DMARC reports.

Rollback to the old interim (Soverin as `Bazibo <mark@westerweel.work>`, Reply-To
hallo@bazibo.nl from the ConfigMap): `scripts/switch-bazibo-smtp.sh --rollback`.

### Why Yourhosting looked unreachable (25-28 Nov 2026)

web-1066 (92.63.174.175, site, FTP and Plesk) **drops our home IPv4 217.63.209.65**: every
port times out from agent-lxc, jumpy and the cluster, while from a GitHub runner the same
host answers on 21/443/8443, and its neighbour web-1065 (92.63.174.173) answers from home.
A TCP traceroute shows our SYNs reach Yourhosting's edge (31.25.97.7) and die at the last
hop. It started after the sslyze scan of 25 Nov (FTPS from the security report already
timed out on 26 Nov 08:17 UTC) and was renewed by a 1-per-minute poll on the evening of
26 Nov. It is the server's own ban (Plesk fail2ban style); a subscription user has no
*IP Address Banning* page in Plesk, so it can only expire or be lifted by Yourhosting.

Why Mark saw no block: the home LAN has native Ziggo IPv6 (prefix from the router's RA),
and his devices reach bazibo.nl over IPv6 (`2a05:1500:702:5:1c00:e8ff:fe00:2717`), which
was never banned. The homelab hosts talked IPv4 only: agent-lxc's `net0` has no `ip6`,
so Proxmox writes `IPv6AcceptRA = false`; the cluster pods have no IPv6 route.

- From agent-lxc, Plesk and the site work over IPv6 once RA is accepted
  (`sudo sysctl -w net.ipv6.conf.eth0.accept_ra=1`; runtime only, gone after a restart).
  Permanent, as root on the Proxmox host: `pct set 210 -net0 <current net0>,ip6=auto`.
- Mail no longer touches web-1066 at all (above), so the IPv4 ban does not matter for codes.
- Still: one request at a time to bazibo.nl and ftp.bazibo.nl, never a loop. The security
  report's FTPS pull (`secreport plesk-reset`) forces IPv4 and stays stopped until the ban
  is gone.

### Switch, verify, roll back

The switch, from agent-lxc in the root of the homelab repo (done on 2026-11-28):

```sh
scripts/check-bazibo-smtp.sh --login   # ONE connection: reachable, TLS, one login
scripts/switch-bazibo-smtp.sh          # one Secret patch + rollout restart
```

- `check-bazibo-smtp.sh` makes exactly one IPv4 connection from inside the netnl pod, with
  one `AUTH PLAIN` under `--login`. It reads the credentials before it connects. It refuses
  to run again for the same host within 6 hours (the guard lives on agent-lxc only). **Never loop it.** Yourhosting's
  firewalls block us for repeated connections.
- `switch-bazibo-smtp.sh` writes `NETNL_BAZIBO_SMTP_HOST/PORT/MODE/USERNAME/PASSWORD/FROM`
  into the Secret `netnl-bridge` in one merge patch. The password comes from OpenBao on
  jumpy over stdin. It refuses without a successful `--login` check in the last 24 h.
  Back to Soverin: `scripts/switch-bazibo-smtp.sh --rollback`.

Verify with one hand-issued code. It is mailed to Mark and never shown:

```sh
ssh jumpy 'kubectl -n netnl exec deploy/netnl -- netnl-admin bazibo mint --mail mark@westerweel.work --ref test-mailfrom-<yyyymmdd-hhmm>'
```

The ref is the idempotency key: a repeated ref mails nothing, so use a new one per test.
The mail lands in Mark's Soverin mailbox (and in Gmail if that fetches it). View the source
(Gmail: *Show original*). It should show `From: Bazibo <hallo@bazibo.nl>`,
`Reply-To: hallo@bazibo.nl`, and `SPF: PASS` and `DKIM: PASS` with domain bazibo.nl. During
the interim it shows `From: Bazibo <mark@westerweel.work>` with SPF and DKIM for
westerweel.work (Soverin). The test code is a real code. Revoke it afterwards:
`ssh jumpy 'kubectl -n netnl exec deploy/netnl -- netnl-admin bazibo revoke <code_id>'`, where
the code id is printed by `mint`.

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
