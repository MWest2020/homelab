# Nodes van 1 naar 4 vCPU brengen

De zes cluster-VM's draaiden op **één vCPU**, terwijl de bedoeling vier
was. Dat valt niet op tot iets niet meer ingepland kan worden: op
2026-09-20 bleven twee habitat-runs anderhalf uur `Pending` staan met
`0/6 nodes are available: 3 Insufficient cpu`, wat op een vastgelopen
build lijkt in plaats van op een vol cluster.

## Waar het aan lag

Niet aan de templates. Die staan alle zes op 4 cores (9001/9002 op
px-01, 9011/9012 op px-02, 9021/9022 op px-03) — nagemeten via de
Proxmox-API.

Het zat in `terraform/k8s-cluster/main.tf`:

```hcl
cpu {
  type = "host"
}
```

De bpg-provider beheert een gedeclareerd `cpu`-blok **in zijn geheel**.
Laat je `cores` weg, dan vult hij zijn eigen default in — 1 — en
overschrijft daarmee de 4 cores die uit de template kwamen. Het blok is
ooit toegevoegd om alleen het cpu-*type* op `host` te zetten (AVX2 voor
de Bun-gebaseerde `claude`-binary); dat het daarmee ook de cores ging
bepalen, was niet de bedoeling.

De regel "hardware-shape komt uit de template" klopt dus nog steeds —
maar een `cpu`-blok is een override, ook als je maar één veld invult.

## De reparatie

`cores = 4` staat nu in dat blok. Daarmee is de bron van waarheid weer
terraform, en zet een volgende `apply` het niet terug.

## Hoeft er iets opnieuw geïnstalleerd te worden?

Nee. Per VM is het: afsluiten, cores zetten, starten. Geen manifest
verandert, geen data verhuist, het cluster blijft draaien zolang je
**één node tegelijk** doet. Een wijziging in het cpu-blok pakt pas na
een volledige stop/start — een reboot ín de gast is niet genoeg.

Wat wél een paar minuten wegvalt: alles met een lokaal volume op díé
node. De opslagklasse is `local-path`, dus zo'n volume ligt vast op één
node en verhuist niet mee:

| node | volumes die zolang stilliggen |
| --- | --- |
| node-01 | `homelab-pg-3`, `netnl-data`, `openbao`, `seaweedfs-data`, `wanderer-data` |
| node-02 | `homelab-pg-1`, `opensearch-data` |
| node-03 | `homelab-pg-2`, `ollama-models`, `wordsworth-corpus` |

Postgres draait met drie instances gespreid, dus één node eruit geeft
daar een failover en geen stilstand.

## Uitvoeren (vanaf jumpy)

De API-token staat in `terraform/k8s-cluster/.env`; ssh naar `root@px-*`
werkt vanaf jumpy niet en is hier ook niet nodig.

```bash
cd ~/homelab && git pull
cd terraform/k8s-cluster && set -a && . ./.env && set +a
terraform plan -target='proxmox_virtual_environment_vm.vm["node-01"]'
```

Dan per VM, **één tegelijk**, in deze volgorde: eerst de workers
(node-01, node-02, node-03), daarna de control planes (cp-01, cp-02,
cp-03). Control planes als laatste, zodat het cluster tijdens het
zwaarste deel een volledige etcd-meerderheid houdt.

```bash
# 1. leeghalen
kubectl drain node-01 --ignore-daemonsets --delete-emptydir-data --timeout=5m

# 2. terraform zet de cores en doet de stop/start
terraform apply -target='proxmox_virtual_environment_vm.vm["node-01"]'

# 3. terug in dienst
kubectl uncordon node-01

# 4. controleren vóór de volgende
kubectl get node node-01 -o jsonpath='{.status.capacity.cpu}{"\n"}'   # 4
kubectl get pods -A --field-selector status.phase!=Running --no-headers
```

Stap 4 is geen formaliteit: een pod met een lokaal volume komt pas
terug als zijn node terug is, en die wil je gezien hebben voordat je de
volgende leeghaalt. `drain` verplaatst zo'n pod niet — dat is verwacht
gedrag bij `local-path` en geen reden voor `--force`.

Voor de control planes hetzelfde recept, met `cp-01` enzovoort. Wacht
tussen twee control planes tot `kubectl get nodes` alle drie weer
`Ready` meldt.

## Daarna

Met 4 cores per node kan de pleister van 2026-09-20 terug:

- `dispatch/job-template.yaml` in de habitat-repo mag weer `cpu: 250m`
  vragen in plaats van 150m;
- de verlaagde verzoeken van keycloak (40m), wanderer (25m), de
  inlogproxy (10m) en de tunnels (5m) mogen ruimer, al is er weinig
  reden toe — ze gebruiken het niet;
- `openanonymiser` hoeft niet teruggeschaald van drie replica's.

Controle tot slot:

```bash
for n in node-01 node-02 node-03; do
  kubectl describe node $n | grep -A4 'Allocated resources' | grep -E '^  cpu'
done
```
