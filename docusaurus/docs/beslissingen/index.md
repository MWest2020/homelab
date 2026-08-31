---
title: Beslissingen
sidebar_position: 1
---

# Beslissingen

De afwegingen achter de architectuur. Hieronder de keuzes die direct uit de repo
(Terraform-modules, Ansible-playbooks, comments) blijken.

## 3 control-plane (HA), nooit 2

etcd en corosync willen een **oneven** quorum. Met 3 control-plane-nodes mag er 1
uitvallen (2/3 quorum blijft) en leeft het cluster door. Met 2 nodes is het quorum
juist slechter dan met 1: elke uitval breekt de meerderheid. Daarom 3 CP-VM's, verdeeld
over 3 fysieke Proxmox-hosts (anti-affinity), met een kube-vip VIP (`192.168.178.201`)
als stabiel control-plane-endpoint.

## Template-per-shape i.p.v. post-clone hardware-overrides

De `k8s-cluster`-Terraform-module bevat **bewust geen** `cpu`/`memory`/`disk`/
`operating_system`-blocks. De bpg Proxmox-provider hangt op post-clone hardware-overrides,
dus de shape komt 100% uit de template. Gevolg: één template per VM-vorm, en de VMID's
zijn cluster-breed uniek (per host een eigen reeks: 9001/9002, 9011/9012, 9021/9022).

## kube-vip VIP als endpoint, niet één CP-adres

De kubeconfig en het control-plane-endpoint wijzen naar de kube-vip VIP
`192.168.178.201`, niet naar een individuele control-plane-node. Zo blijft het cluster
bereikbaar als de node achter een vast adres wegvalt. De VIP zit bewust **niet** in
Terraform (`var.vms`) — die wordt door Ansible/kube-vip beheerd.

## local-lvm i.p.v. gedeelde storage

Storage is `local-lvm` per Proxmox-node. Geen Ceph: dat is binnen homelab-scope te veel
overhead. HA wordt op cluster-niveau (etcd-quorum + anti-affinity over hosts) opgelost,
niet op storage-niveau.

## CrowdSec detection-only first, gedeeld logbestand i.p.v. docker.sock

CrowdSec op de proxy is bewust **detection-only** begonnen (fase A.1): de engine parste
Caddy's access-log en genereerde alleen alerts, zonder bouncer. Zo zag je eerst wat een
bouncer zou tegenhouden, vóórdat je het risico op false-positive-blocks op de publieke
surface nam.

De engine leest het access-log via een **gedeelde, read-only host-bind-mount**, niet via
`docker.sock`: een logbestand is auditbaarder en veel minder geprivilegieerd dan
socket-toegang tot de Docker-daemon.

## CrowdSec-bouncer: Caddy-L7-plugin i.p.v. firewall-bouncer

Sinds fase A.2 (live op .50) wordt er **wél geblokkeerd**. Gekozen is de
**Caddy-L7-plugin** (`hslatman/caddy-crowdsec-bouncer`), niet `cs-firewall-bouncer`. De
plugin handelt het blokkeren af in Caddy zelf — een nette 403 per vhost, in dezelfde
request-flow als de TLS-terminatie en logging — zonder iptables-regels op de host te
manipuleren. Dat past op de Caddy-native architectuur en is auditbaarder dan een
firewall-laag die los van de proxy leeft. De bouncer faalt bovendien **open**: valt de
LAPI weg, dan blijft Caddy verkeer doorlaten i.p.v. de publieke proxy mee te slepen.

Nog bewust uitgesteld: deelname aan de **community-blocklist** (CAPI), en de
**client-IP-herkenning** (`trusted_proxies`/XFF) — zonder die laatste ziet CrowdSec achter
de Docker-`userland-proxy` alleen de RFC1918-bridge-gateway. Beide worden opgepakt vóór de
proxy echt scherp publiek gaat.

## App-of-apps + sync-waves i.p.v. losse `kubectl apply`

Alle cluster-apps hangen onder één Argo CD root-Application (`apps/root-app.yaml`).
Volgorde-afhankelijkheden (operator vóór CR, storage vóór consumer) worden expliciet
gemaakt met **sync-waves** in plaats van impliciet met apply-volgorde: de CNPG-operator
(wave 2) moet healthy zijn vóór het `homelab-pg`-Cluster-CR (wave 4), en Wordsworth
(wave 6) komt pas als DB, S3 en de model-services er staan. Operators met CRDs groter
dan de 256KB `last-applied`-annotation (CNPG, Tailscale) syncen met `ServerSideApply`.

## RAG volledig in-cluster ("sovereign") i.p.v. externe AI-API's

De Wordsworth-straat gebruikt bewust géén externe LLM- of embedding-API: Ollama draait de
modellen lokaal (CPU-only, dus traag maar soeverein), OpenSearch is de index en
OpenAnonymiser redigeert PII — alles ClusterIP, niets verlaat het lab. De trade-off is
snelheid: een klein model (`llama3.2:3b`) en minuten-lange cold-starts zijn de prijs voor
documenten die nooit naar een derde partij gaan.

## Tailnet-intern exposen i.p.v. publiek via de Gateway

De Wordsworth-API is bereikbaar via de Tailscale-operator (`loadBalancerClass:
tailscale`), niet via de publieke Gateway. Een RAG-API over eigen documenten heeft geen
publieke surface nodig; tailnet-membership ís de authenticatie. De OAuth-credentials van
de operator leven in een out-of-band Secret — nooit in Git.

Voor de browser-based **Wordsworth Console** (GitHub Pages) kwam daar een
**tailnet-private HTTPS-Ingress** bij (MagicDNS-cert): een https-pagina mag geen
http-API aanroepen (mixed content). Bewust **zonder** `tailscale.com/funnel`-annotatie
— dit is soevereine PII-infra en blijft binnen de tailnet; CORS staat alleen open voor
de Console-origin. Tailnet-membership blijft de buitenste schil; daarbinnen is
caller-auth (API-keys) opt-in aangezet als tweede laag.

## Reversibel pseudonimiseren met eigen key store (OpenBao) i.p.v. onomkeerbaar redigeren

Fase B van de Wordsworth-straat vervangt PII niet langer onomkeerbaar: per ingest worden
data-keys aangemaakt die **OpenBao-Transit-wrapped** in de database liggen. De KEK zelf
verlaat OpenBao nooit; Wordsworth krijgt alleen een scoped token dat onder die ene KEK
mag wrappen/unwrappen — geen root-rechten. Redactie blijft de standaard, maar herleiding
is mogelijk voor wie daar recht op heeft — zonder externe KMS, passend bij de
soevereiniteits-keuze hierboven.

De kroonjuwelen (unseal-key + root-token) ontstaan alleen in de terminal van de operator
— nooit in Git, het cluster of een agent-context. Lab-compromis: de unseal-key staat wél
als Secret in etcd, zodat een `postStart`-hook na pod-restarts automatisch unsealt en de
straat zichzelf heelt. Productie moet echte auto-unseal gebruiken (Transit vanaf een
tweede instance, of een HSM/KMS) en nooit een statische unseal-key mounten.

## OpenAnonymiser: chunking + horizontaal schalen i.p.v. één grote pod

GLiNER's attention groeit kwadratisch met de documentlengte: hele documenten in één call
joegen de pod door zijn geheugen heen (OOM-loops). De oplossing is tweeledig: de
**client chunkt** (kleine calls begrenzen het geheugen per call) en de service schaalt
**horizontaal** — 3 replica's, één per worker, zodat de chunks van één document over de
cluster-CPU's uitwaaieren. Daardoor konden de memory-limits juist omlaag en past de
service naast OpenSearch, Ollama en Postgres op de 16Gi-workers.

Bijvangst van 1-CPU-workers: de health-endpoint blokkeert tijdens inference, dus
readiness/liveness zijn **TCP-probes** — een drukke pod blijft in de endpoints en wordt
niet gekilld; een écht hangend proces accepteert ook geen connecties meer.

## PostgreSQL via CNPG-operator i.p.v. handmatige StatefulSet

CloudNativePG beheert `homelab-pg`: 3 instances met anti-affinity over de workers
(`preferred`, niet `required` — bij node-uitval liever herstarten op een andere node dan
eeuwig Pending), digest-gepinde PG17-image, en app-credentials die de **operator zelf
genereert** — geen handmatig secret, geen plaintext in Git. Failover en switchover zijn
operator-logica in plaats van runbook-stappen.

## SeaweedFS i.p.v. MinIO achter de S3-seam

MinIO's open-source-editie is dood: binaries gestopt in oktober 2025, repo gearchiveerd
op 2026-04-25 — geen security-updates meer. Omdat alle consumers via een **generieke
S3-seam** praten (endpoint + credentials in env, path-style), was de vervanger een
endpoint-flip, geen herbouw. Gekozen is **SeaweedFS** (`weed server -s3`): al CI-bewezen
in de wordsworth-testsuite, en een statische Go-binary zonder de glibc-x86-64-v2-eis
die MinIO had. De migratie liep in drie gearchiveerde OpenSpec-changes (2026-08-27):

1. **wordsworth** — rclone-sync van de bucket, 414 objecten checksum-gelijk, daarna
   endpoint-flip in de ConfigMap.
2. **cluster-MinIO eruit** — de enige andere bucket (`nextcloud`) bleek leeg
   (nextcloud-platform is nooit ge-applied), dus niets hield MinIO nog in leven.
3. **buzz-relay** — dezelfde swap in de compose-stack op de VM (21 objecten, 0 diff).

Ceph RGW blijft het lange-termijndoel; de S3-seam maakt die latere swap identiek aan
deze. De oude situatie staat in het [Archief](../archief/).

## netnl: facade in-cluster, batch-instance op de VPS

De Internet.nl-batch-instance vereist een **vast publiek IPv4+IPv6** — dat kan een
ge-NAT homelab niet leveren, dus de instance draait op een VPS (tailnet-only
afgeschermd). De **facade** (tenant-auth, retention, provenance) draait wél in-cluster:
daar is de GitOps-machinerie, en de VPS houdt maar één taak. Drie afgeleide keuzes:

- **Twee publieke ingangen, dezelfde facade.** De Tailscale Funnel was er eerst
  (nul extra infra: geen Caddy-edge, geen port-forward); de **Cloudflare Tunnel** kwam
  erbij voor de merknaam `api.westerweel.work`. Beide outbound-only — de router blijft
  dicht.
- **Egress via CoreDNS-rewrite, niet via hostAliases.** De instance-nginx doet strikte
  SNI, dus de facade móet de echte hostnaam gebruiken. Een gepind ClusterIP +
  `hostAliases` brak omdat de tailscale-operator de egress-Service naar `ExternalName`
  muteert; een CoreDNS-rewrite volgt de Service-naam en overleeft dat. De Argo CD-app
  heeft `ignoreDifferences` op de Service-spec zodat selfHeal en de operator niet om
  de spec vechten.
- **Upstream-credential out-of-band** (Secret `netnl-upstream`), zelfde patroon als
  wordsworth; OpenBao-injectie is de latere hardening-stap.

## Vendored compose verbatim; afwijkingen gesanctioneerd én gemarkeerd

De buzz-relay-compose is **verbatim vendored** van upstream block/buzz, met als regel
"niet lokaal aanpassen" — zo blijft een upstream-upgrade een simpele nieuwe kopie.
Afwijken mag alleen **gesanctioneerd** (expliciet besluit, gelogd in OpenSpec/CHANGELOG)
en **gemarkeerd in de file-header**, zodat de afwijking bij een upgrade bewust opnieuw
wordt aangebracht i.p.v. stilletjes te verdwijnen. Tot nu toe twee: het cpu-type
(2026-07-06, MinIO's glibc-eis — kan terug naar default nu MinIO weg is) en de
SeaweedFS-swap (2026-08-27).

## Images pinnen op commit-SHA, deploys als Git-commits

Wordsworth-images worden gepind op een commit-SHA-tag (`ghcr.io/...:sha-<commit>`), nooit
`latest`. Elke deploy is daarmee een zichtbare Git-commit (`deploy(wordsworth): pin
sha-...`) — reproduceerbaar, bisect-baar en terug te rollen met een revert.

## Docs extern gehost, niet in-cluster

Deze kennisbank (Docusaurus, statische build) wordt **buiten** het cluster gehost, zodat
ze leesbaar blijft als het cluster zelf onbereikbaar is — juist tijdens een incident
wanneer je de runbooks nodig hebt.
