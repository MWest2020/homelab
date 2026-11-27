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
| DKIM / DMARC | signing on in Plesk (selector `default`); `_dmarc`, `_domainkey` and `default._domainkey` published | `default._domainkey` seen in DNS on 2026-11-27 (below) |
| Code mails (netnl) | the netnl facade mails Bazibo unlock codes; interim via Soverin, target `mail.bazibo.nl:587` | [below](#bazibo-code-mail-from-netnl) |
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
whitespace in `p=` and verifiers strip it, so it should verify. Still to check (Plesk was
unreachable on 2026-11-27, see below): that this key equals the one in Plesk
(Mail-instellingen › bazibo.nl › Het instellen van externe DNS). Join the quoted chunks of the
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

### Now (interim): Soverin, Bazibo name, Bazibo reply address

- No `NETNL_BAZIBO_SMTP_HOST`, so the code mail goes through Soverin.
- From: `Bazibo <mark@westerweel.work>`. The address falls back to `NETNL_SMTP_FROM`, and
  the display name defaults to "Bazibo".
- `NETNL_BAZIBO_MAIL_REPLY_TO: hallo@bazibo.nl` is in the ConfigMap, so a buyer's reply
  reaches the forwarder and then Mark.
- Soverin sends only as addresses on its own account. A custom domain has to be added to
  the account, with its MX/SPF/DKIM pointing at Soverin. bazibo.nl's mail lives at
  Yourhosting, so `From: hallo@bazibo.nl` through Soverin was not tried.

### Target: mail.bazibo.nl:587, From `Bazibo <hallo@bazibo.nl>`

Three things block it, all on Mark's side:

1. **Yourhosting firewall.** Since 26 Nov 2026, 92.63.174.175 (web/mail/Plesk) refuses the
   home IP **217.63.209.65**. TCP 587 times out from the cluster. Ask Yourhosting support to
   whitelist 217.63.209.65 for web-1066.yourhosting.nl (SMTP submission 587 and Plesk 8443).
   Mention that the block followed repeated connection attempts from that address, which
   have stopped.
2. **SMTP login for hallo@bazibo.nl.** It is a forwarder without a mailbox. Plesk keeps such
   an account out of its mail authorization database, so SMTP AUTH fails ("No such user …
   in mail authorization database"). Fix: in Plesk → Mail → `hallo@bazibo.nl` → tab
   *Algemeen*, tick **Mailbox** with a normal size (not 0 MB: a 0 MB mailbox bounces
   incoming mail while still forwarding it), and keep *Doorsturen* to mark@westerweel.work
   on. Copies of forwarded mail then pile up in the mailbox, so empty it now and then
   (webmail) or give it a small size such as 100 MB. The password stays the one in
   OpenBao. Alternative: a separate send-only mailbox. That needs a new OpenBao entry, and
   Plesk may then refuse `From: hallo@` for another login, so enabling the mailbox is
   simpler.
3. **DKIM.** Compare the published `default._domainkey` key with Plesk (above). Without a
   matching key, mails from mail.bazibo.nl fail DKIM and lean on SPF alone (`a` covers
   92.63.174.175).

When 1 and 2 are done, from agent-lxc in the root of the homelab repo:

```sh
scripts/check-bazibo-smtp.sh --login   # ONE connection: reachable, STARTTLS, one login
scripts/switch-bazibo-smtp.sh          # one Secret patch + rollout restart
```

- `check-bazibo-smtp.sh` makes exactly one IPv4 connection from inside the netnl pod, with
  one `AUTH PLAIN` under `--login`. It reads the credentials before it connects. It refuses
  to run again for the same host within 6 hours (the guard lives on agent-lxc only). **Never loop it.** Yourhosting's
  firewall blocks us for repeated connections.
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
