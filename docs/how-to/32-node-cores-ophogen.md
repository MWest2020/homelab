# Nodes van 1 naar 4 vCPU brengen

De zes cluster-VM's draaien op **één vCPU**, terwijl de bedoeling vier was.
`terraform/k8s-cluster/variables.tf` zegt het zelf:

```
template_vm_id = number # per-shape template: bv. CP=9001 (4c/8GB/50GB), worker=9002 (4c/16GB/50GB)
```

Het geheugen uit die templates is wél doorgekomen (8 GB voor de control
planes, 16 GB voor de workers), de cores niet. Dat valt niet op tot iets
niet meer ingepland kan worden — op 2026-09-20 bleven twee habitat-runs
anderhalf uur `Pending` staan met
`0/6 nodes are available: 3 Insufficient cpu`, en dat lijkt op een
vastgelopen build in plaats van een vol cluster.

## Hoeft er iets opnieuw geïnstalleerd te worden?

Nee. Dit is per VM: afsluiten, cores omzetten, starten. Het cluster
blijft draaien zolang je **één node tegelijk** doet. Niets wordt
opnieuw uitgerold, geen data verplaatst, geen manifest gewijzigd.

Wat wél tijdelijk weg is: alles wat op díé node een lokaal volume heeft.
De opslagklasse is `local-path`, dus een volume ligt vast op één node en
verhuist niet mee. Zo lag het op 2026-09-20:

| node | volumes die zolang stilliggen |
| --- | --- |
| node-01 | `homelab-pg-3`, `netnl-data`, `openbao`, `seaweedfs-data`, `wanderer-data` |
| node-02 | `homelab-pg-1`, `opensearch-data` |
| node-03 | `homelab-pg-2`, `ollama-models`, `wordsworth-corpus` |

Postgres staat met drie instances verspreid, dus één node eruit betekent
daar een failover en geen stilstand. Voor de rest geldt: die dienst is
een paar minuten weg. Controleer daarom vóór elke node of de vorige
weer volledig terug is.

## De templates eerst

Zet de templates goed, anders komt de volgende kloon weer op één core
uit. Op de Proxmox-host:

```bash
qm set 9001 --cores 4      # control-plane-shape
qm set 9002 --cores 4      # worker-shape
```

## Per node, één tegelijk

```bash
# 1. leeghalen (vanaf een host met kubectl)
kubectl drain node-01 --ignore-daemonsets --delete-emptydir-data --timeout=5m

# 2. op de Proxmox-host: netjes afsluiten, cores zetten, starten
qm shutdown <vmid> && sleep 20
qm set <vmid> --cores 4
qm start <vmid>

# 3. terug in dienst nemen
kubectl uncordon node-01

# 4. controleren vóór je de volgende doet
kubectl get node node-01 -o jsonpath='{.status.capacity.cpu}{"\n"}'   # 4
kubectl get pods -A --field-selector status.phase!=Running --no-headers
```

Stap 4 is geen formaliteit: een pod met een lokaal volume komt pas terug
als zijn node terug is, en die wil je gezien hebben voordat je de
volgende node leeghaalt.

`drain` verplaatst pods met een lokaal volume niet — die worden gestopt
en komen terug zodra de node er weer is. Dat is verwacht gedrag bij
`local-path` en geen reden om `--force` te gebruiken.

## Daarna

Met 4 cores per node kan de pleister van 2026-09-20 terug:

- `dispatch/job-template.yaml` in de habitat-repo mag weer `cpu: 250m`
  vragen in plaats van 150m;
- de CPU-verzoeken van keycloak (40m), wanderer (25m), de inlogproxy
  (10m) en de tunnels (5m) mogen ruimer, al is er weinig reden toe —
  ze gebruiken het niet;
- `openanonymiser` hoeft niet teruggeschaald van drie replica's.

Controleer tot slot dat het cluster weer lucht heeft:

```bash
for n in node-01 node-02 node-03; do
  kubectl describe node $n | grep -A4 'Allocated resources' | grep -E '^  cpu'
done
```
