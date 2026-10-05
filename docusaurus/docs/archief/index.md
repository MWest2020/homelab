---
title: Archief
sidebar_position: 1
---

# Archief

Historie — bewaard, niet weggegooid: hoe de homelab eruitzag vóór het Proxmox-cluster,
en onderdelen die sindsdien vervangen zijn.

## Baremetal "Kubernetes the Hard Way"

De eerste opzet draaide Kubernetes **direct op baremetal**, handmatig opgezet volgens
[Kubernetes the Hard Way](https://github.com/kelseyhightower/kubernetes-the-hard-way) —
bewust gekozen voor maximaal begrip van de losse onderdelen (systemd-units, certs,
etcd, kubelet) i.p.v. een kant-en-klare installer.

- **Hardware:** 3× HP EliteDesk Mini-PC's.
- **Topologie:** één control-plane + twee workers, direct op de fysieke machines —
  cp-01 (`192.168.178.201`), node-01 (`192.168.178.202`), node-02 (`192.168.178.203`).
- **Versies:** Kubernetes v1.29.2, Cilium 1.19.0, CoreDNS als cluster-DNS.
- Eén control-plane, dus **geen HA**: uitval van die node legde de API-server plat.

## Migratie: Hard Way → kubeadm

Het handmatige cluster is vervangen door een **kubeadm**-cluster op dezelfde hosts —
geen twee clusters naast elkaar (één kubelet per node), dus een vervanging met korte
downtime. De jumpbox, hostnamen en IP's bleven gelijk; alleen de clusterinhoud werd
opnieuw opgezet. Dit bracht de provisioning onder Ansible (`prepare-nodes` →
`kubeadm-install-packages` → `kubeadm-bootstrap` → `kubeadm-post-bootstrap`) in plaats
van de handmatige systemd-stappen.

## Naar het Proxmox-VM-cluster

Daarna is de homelab verhuisd van baremetal naar het huidige **3-node Proxmox-cluster
met HA-Kubernetes op VM's** (3 control-plane + 3 workers, kube-vip VIP `.201`). Daarmee
verdween het single-control-plane-model: virtualisatie ontkoppelt hardware van workload
en maakt anti-affinity over 3 fysieke machines mogelijk. De huidige staat staat onder
[Architectuur](../architectuur/).

## MinIO als S3-store (maart – augustus 2026)

Het cluster draaide **MinIO** als S3-compatibele object storage (Helm-deploy, 50Gi PVC,
namespace `minio`) — in maart 2026 neergezet voor een geplande Nextcloud-deploy, en
vanaf augustus 2026 pragmatisch ook het S3-endpoint van de Wordsworth-straat. De
buzz-relay-VM draaide daarnaast een eigen MinIO in z'n compose-stack.

MinIO's open-source-editie werd echter gearchiveerd (2026-04-25, geen security-updates
meer). Op **2026-08-27** is alles naar SeaweedFS gemigreerd en is MinIO overal
verwijderd — wordsworth-data checksum-geverifieerd overgezet (414 objecten), de
nextcloud-bucket bleek leeg, buzz-relay's media idem gemigreerd (21 objecten). De
afwegingen staan onder [Beslissingen](../beslissingen/); de uitvoering in de
gearchiveerde OpenSpec-changes van 2026-08-27 in de repo.

## Buzz-relay: vendored compose in deze repo (juli – september 2026)

De compose-stack van de buzz-relay-VM stond eerst in deze repo (`docker/buzz-relay/`),
**verbatim vendored** van upstream block/buzz. De regel was "niet lokaal aanpassen",
zodat een upstream-upgrade een simpele nieuwe kopie bleef. Afwijken mocht alleen
**gesanctioneerd** (expliciet besluit, gelogd in OpenSpec/CHANGELOG) en **gemarkeerd in
de file-header**, zodat de afwijking bij een upgrade bewust opnieuw werd aangebracht in
plaats van stilletjes te verdwijnen. Er waren er twee: het cpu-type (2026-07-06,
MinIO's glibc-eis) en de SeaweedFS-swap (2026-08-27).

Sinds 2026-09-11 komt de stack uit
[MWest2020/ratatoskr `deploy/`](https://github.com/MWest2020/ratatoskr/tree/main/deploy).
Op 2026-09-24 zijn de oude kopie en de systemd-unit `boomhuis-chat.service` hier
verwijderd: er waren twee manieren om de chat te draaien, en één daarvan was dood.

## Wordsworth-straat op één node (tot september 2026)

Tot de wordsworth-change *hoge-beschikbaarheid* draaide elk onderdeel van de straat
als één pod: OpenSearch als single-node-Deployment, Ollama als één Deployment waarvan
een **PostSync-hook-Job** de modellen pullde via de Service, op zwevende tags. Het
nieuwe model staat onder [Architectuur](../architectuur/), het waarom onder
[Beslissingen](../beslissingen/).

- **Ollama**: op 2026-09-26 vervangen door twee instances met digest-gepinde modellen.
- **OpenSearch**: sinds 2026-09-26 zoekt Wordsworth op het cluster van drie nodes. De
  single-node (Deployment `opensearch`, `Recreate`, één 10Gi-volume `opensearch-data`,
  `discovery.type: single-node`) bleef een week staan als rollback en is op
  **2026-10-03** verwijderd, met zijn volume. De index was vooraf gekopieerd met
  reindex-from-remote.
- **Ollama-limit 5Gi** (tot 2026-09-28): te krap voor twee geladen modellen, wat twee
  gelijktijdige `/ask`-calls op 2026-09-26 met een OOM-kill van beide pods aantoonden.
  Nu 7Gi, gemeten.

## Nextcloud-tenants op Docker (laptop-node)

Naast het K8s-cluster draaien Nextcloud-tenants als Docker-compose-stacks op VM's op de
laptop-Proxmox-node, met een Caddy-proxy ervoor (hostname-routing + TLS). Dit is geen
historie maar een parallel spoor; het staat hier genoteerd omdat het buiten het
K8s-cluster valt.
