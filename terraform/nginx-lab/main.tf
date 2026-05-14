resource "proxmox_virtual_environment_vm" "vm" {
  for_each  = var.vms
  name      = each.key
  node_name = "proxmox"
  vm_id     = each.value.vm_id
  started   = true

  clone {
    vm_id = 9000
    full  = true
  }

  cpu {
    cores = each.value.cores
    type  = "host"
  }

  memory {
    dedicated = each.value.memory
  }

  # Resize de gecloonde template-disk (default 3.5GB) naar each.value.disk GB.
  # interface = scsi0 moet matchen met de template; anders maakt bpg een 2e disk
  # ipv. te resizen. Cloud-init growpart breidt partition + ext4 auto uit op boot.
  disk {
    datastore_id = "local-lvm"
    interface    = "scsi0"
    size         = each.value.disk
  }

  network_device {
    bridge = "vmbr0"
    model  = "virtio"
  }

  initialization {
    datastore_id = "local-lvm"

    ip_config {
      ipv4 {
        address = "${each.value.ip}/24"
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
    type = "l26"
  }

  agent {
    enabled = false
  }
}

output "vm_ips" {
  value = { for name, vm in var.vms : name => vm.ip }
}
