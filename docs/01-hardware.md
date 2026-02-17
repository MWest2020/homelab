# Hardware Specificaties

## Nodes

### Control Plane - `cp-01`
| Spec | Waarde |
|------|--------|
| Model | HP EliteDesk 800 G? Mini |
| CPU | Intel Core i?-???? |
| RAM | 32GB DDR4 |
| Storage | ?GB NVMe/SSD |
| IP | `<CONTROL_PLANE_IP>` |
| Rol | Kubernetes Control Plane |

### Worker 1 - `node-01`
| Spec | Waarde |
|------|--------|
| Model | HP EliteDesk 800 G? Mini |
| CPU | Intel Core i?-???? |
| RAM | 32GB DDR4 |
| Storage | ?GB NVMe/SSD |
| IP | `<WORKER_01_IP>` |
| Rol | Kubernetes Worker |

### Worker 2 - `node-02`
| Spec | Waarde |
|------|--------|
| Model | HP EliteDesk 800 G? Mini |
| CPU | Intel Core i?-???? |
| RAM | 32GB DDR4 |
| Storage | ?GB NVMe/SSD |
| IP | `<WORKER_02_IP>` |
| Rol | Kubernetes Worker |

> **Note**: IP adressen staan in `.env` (niet in Git). Zie `.env.example` voor template.

## Jumpbox / Management

Je lokale machine (Windows + WSL2) fungeert als jumpbox:
- kubectl geconfigureerd met `~/.kube/config`
- Ansible runt vanaf hier
- Toegang tot cluster via SSH en kubectl

## Waarom HP EliteDesk Mini's?

- **Bedrijfsklasse hardware**: Gemaakt voor 24/7 operatie
- **Laag stroomverbruik**: ~35W TDP, ideaal voor always-on
- **Compact formaat**: Stapelbaar, weinig ruimte nodig
- **Stilte**: Ontworpen voor kantooromgevingen
- **vPro support**: Remote management mogelijkheden (indien aanwezig)

## TODO

- [ ] Exacte modelnummers invullen na installatie
- [ ] CPU specs ophalen (`lscpu`)
- [ ] Storage specs ophalen (`lsblk`)
- [ ] BIOS versies documenteren
