# Random initial root password — used once for the very first console / qm enter
# session if the operator ever needs to recover. Normal access path is SSH-key.
# Read once via: terraform output -raw root_initial_password
resource "random_password" "root" {
  length  = 32
  special = true
}

resource "proxmox_virtual_environment_container" "agent_lxc" {
  vm_id     = var.vm_id
  node_name = var.node_name

  # Unprivileged is the secure default; combined with nesting it still lets
  # Tailscale create its tun device via the explicit /dev/net/tun passthrough
  # below.
  unprivileged = true

  start_on_boot = true
  started       = true

  operating_system {
    template_file_id = var.template_file_id
    type             = "ubuntu"
  }

  initialization {
    hostname = var.hostname

    ip_config {
      ipv4 {
        address = "${var.static_ip}/${var.cidr}"
        gateway = var.gateway
      }
    }

    dns {
      servers = ["192.168.178.1", "8.8.8.8"]
    }

    user_account {
      password = random_password.root.result
      keys     = [trimspace(file(pathexpand(var.ssh_public_key_path)))]
    }
  }

  cpu {
    cores = var.cores
  }

  memory {
    dedicated = var.memory_mb
    swap      = var.swap_mb
  }

  disk {
    datastore_id = var.rootfs_storage
    size         = var.rootfs_size_gb
  }

  network_interface {
    name   = "eth0"
    bridge = var.bridge
  }

  features {
    # Required for Tailscale to use /dev/net/tun inside an unprivileged LXC.
    nesting = true
  }

  # Pass /dev/net/tun into the container so Tailscale's userspace daemon can
  # create its tun device. bpg/proxmox 0.106+ supports this natively for LXC.
  # If a future provider version changes this schema and apply fails, the
  # runbook documents the equivalent manual `pct set 210 -dev0` fallback.
  device_passthrough {
    path = "/dev/net/tun"
  }
}
