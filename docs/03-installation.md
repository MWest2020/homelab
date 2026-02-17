# Ubuntu Server Installatie

## Pre-installatie Checklist

- [ ] USB stick geflasht met Ubuntu Server 24.04 LTS
- [ ] Alle nodes aangesloten via ethernet
- [ ] Monitor en toetsenbord beschikbaar
- [ ] IP adressen gereserveerd (of DHCP reservations gemaakt)

## Installatie Stappen

### 1. Boot van USB
- Steek USB in een **blauwe poort** (USB 3.0) voor snellere installatie
- F9 of F12 voor boot menu (afhankelijk van BIOS)

### 2. Taal en Keyboard
- English (of Nederlands naar voorkeur)
- Keyboard: Dutch of US International

### 3. Installatie Type
- **Ubuntu Server** (niet minimized)

### 4. Netwerk Configuratie
Kies voor handmatige configuratie. Gebruik de waarden uit je `.env` file.

**Control Plane (cp-01):**
```
Subnet: <NETWORK_SUBNET>
Address: <CONTROL_PLANE_IP>
Gateway: <GATEWAY_IP>
Name servers: 1.1.1.1,8.8.8.8
Search domains: (leeg laten)
```

**Worker 1 (node-01):** Zelfde, maar Address: `<WORKER_01_IP>`
**Worker 2 (node-02):** Zelfde, maar Address: `<WORKER_02_IP>`

> Zie `.env.example` voor de variabele namen.

### 5. Storage
- **Use an entire disk** ✓
- Geen LVM nodig voor deze setup
- Wis alles wat er op staat

### 6. Profiel Setup
```
Your name: <SSH_USER>
Server name: cp-01 (node-01, node-02 voor de workers)
Username: <SSH_USER>
Password: [sterk wachtwoord - bewaar veilig!]
```

> ⚠️ Gebruik hetzelfde username op alle nodes voor Ansible!

### 7. SSH Setup
- **Install OpenSSH server** ✓
- Import SSH identity: (optioneel, kan later via Ansible)

### 8. Featured Snaps
- **Skip alles** - we installeren later wat we nodig hebben

### 9. Installatie Voltooien
- Reboot
- Verwijder USB stick
- Verify SSH access: `ssh <SSH_USER>@<CONTROL_PLANE_IP>`

## Post-installatie

Zie [Post-installatie Hardening](04-post-install.md) voor de volgende stappen.

## Troubleshooting

### "ALT driver" melding tijdens boot
Geen zorgen - dit is meestal een USB-C/DisplayPort adapter die even sputert. Geen impact op de installatie.

### Netwerk niet bereikbaar na installatie
1. Check kabelverbinding
2. Verify IP met `ip addr`
3. Check gateway met `ip route`
4. Test DNS met `ping 1.1.1.1` vs `ping google.com`
