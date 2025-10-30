# README 01 — Prepare the Nodes (UEFI, Ubuntu, Network, Storage)

This document describes how to prepare the **three mini‑PCs** (UEFI boot, Ubuntu Server 24.04 LTS, network config, storage, OpenSSH). It captures exactly what we did so you can commit it as a reference.

## Hardware & cabling (first time setup)
- **Switch**: Port **1** = uplink to your **TP‑Link extender/router**.  
- **Nodes**: `node1` → Port **2**, `node2` → Port **3**, `node3` → Port **4**.  
- **Laptop**: Port **8** (or Wi‑Fi on the same LAN).  
- **Monitor & keyboard** temporarily on each mini‑PC. Video via **DisplayPort** (or DP→HDMI adapter).

## Boot & installer
1. Create a **Ventoy USB** and copy the Ubuntu ISO onto it:  
   - Ventoy: https://www.ventoy.net/en/download.html  
   - Ubuntu Server 24.04 LTS: https://ubuntu.com/download/server  
   - Ventoy usage: make the USB bootable once, then simply **copy** ISOs to it. In Ventoy’s menu, pick the ISO.
2. Boot the mini‑PC in **UEFI** mode: during power‑on press **F9** → choose **UEFI: <your USB>**. (*Do not use Legacy*.)  
   - In Ventoy choose **Boot → Normal mode** (only use GRUB fallback if Normal fails).
3. **Ubuntu installer**:
   - **Network configuration**: select **`eno1`**. DHCP is fine. (You can add DHCP reservations later.)  
   - **Proxy**: empty. **Mirror**: default.  
   - **Storage**: *Guided – use entire disk*, enable **LVM**. You’ll often see `ubuntu-vg 100G` and the rest as “free space”; this is **intentional** (expand later).  
   - **Encryption (LUKS)**: optional. For a homelab you can skip; with LUKS you must type the **passphrase** on console at every boot.  
   - **Software**: tick **OpenSSH server**. *Nothing else* (no Docker/PowerShell).
4. Reboot. (With LUKS: enter the passphrase.) Log in locally or via SSH with **username/password** (first time only).

## Post‑install basics (each node)
```bash
sudo apt update && sudo apt -y upgrade
sudo apt -y install vim htop git curl jq unzip
```

## Hostnames & IPs (your current LAN)
- **Hostnames**: `node1`, `node2`, `node3`  
- **IPs (DHCP for now; add reservations later):**  
  - `node1` → `10.0.0.9`  
  - `node2` → `10.0.0.8`  
  - `node3` → `10.0.0.7`

> Tip — If you prefer **static**:
>
> ```yaml
> sudo nano /etc/netplan/01-net.yaml
> network:
>   version: 2
>   ethernets:
>     eno1:
>       addresses: [10.0.0.9/24]
>       routes:
>         - to: default
>           via: 192.168.178.1
>       nameservers:
>         addresses: [1.1.1.1,8.8.8.8]
> sudo netplan apply
> ```
>
> Then set `.108` and `.107` for `node2` and `node3` respectively.

## Status checks
```bash
ip -4 a show eno1 | grep inet
ping -c2 1.1.1.1 && ping -c2 ubuntu.com
```


