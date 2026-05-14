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

  # Disk-grootte komt uit template 9000 (nu 20.5GB na 'qm resize'). Geen disk{}
  # block hier — bpg zou anders elke apply een resize-call doen, ook al matcht
  # de grootte al. Single source of truth = de template.

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
