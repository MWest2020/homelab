resource "proxmox_virtual_environment_vm" "vm" {
  for_each  = var.vms
  name      = each.key
  node_name = "proxmox"
  vm_id     = each.value.vm_id
  started   = true

  clone {
    vm_id = 9002 # ubuntu-24.04-large: 4c/8GB/50.5GB (9001 = k8s-cp-template)
    full  = true
  }

  # GEEN memory/disk/operating_system blocks — alles komt uit template 9002.
  # Zie terraform/nginx-lab/main.tf en docs/how-to/07-vm-provisioning-stack.md:
  # hardware-shape leeft in de template, per-VM config in initialization.
  #
  # cpu type "host" is de gesanctioneerde uitzondering (CHANGELOG 2026-07-06):
  # het qm-default CPU-model mist x86-64-v2 en daar crasht MinIO's glibc op.
  cpu {
    type = "host"
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

  agent {
    enabled = false
  }
}

output "vm_ips" {
  value = { for name, vm in var.vms : name => vm.ip }
}
