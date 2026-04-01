resource "proxmox_virtual_environment_vm" "nextcloud" {
  name      = "nextcloud"
  node_name = "proxmox"
  vm_id     = 100

  # Clone from the Ubuntu 24.04 cloud template
  clone {
    vm_id = 9000
    full  = true
  }

  cpu {
    cores = 2
    type  = "host"
  }

  memory {
    dedicated = 4096
  }

  # Resize the cloned disk to 20GB
  disk {
    datastore_id = "local-lvm"
    interface    = "scsi0"
    size         = 20
    discard      = "on"
  }

  network_device {
    bridge = "vmbr0"
    model  = "virtio"
  }

  # Cloud-init: inject SSH key, static IP, hostname
  initialization {
    datastore_id = "local-lvm"

    ip_config {
      ipv4 {
        address = var.vm_ip
        gateway = var.vm_gateway
      }
    }

    dns {
      servers = ["192.168.178.1", "8.8.8.8"]
    }

    user_account {
      username = "ubuntu"
      keys     = [var.ssh_public_key]
    }
  }

  operating_system {
    type = "l26" # Linux kernel 2.6+
  }

  # Cloud images don't have qemu-guest-agent pre-installed.
  # Disable so Terraform doesn't wait for agent confirmation after boot.
  agent {
    enabled = false
  }
}

output "nextcloud_ip" {
  value = var.vm_ip
}
