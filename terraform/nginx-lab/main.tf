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

  # GEEN cpu/memory/disk/operating_system blocks — alles komt uit template 9000.
  # bpg's post-clone state-machine hangt zodra ie eerst memory/cpu/etc. moet
  # her-pushen voor ie aan initialization toekomt. Door alleen per-VM-specifieke
  # dingen (IP, user, key) in initialization te zetten, doet bpg post-clone
  # exact 1 batch qmset + 1 qmstart. Template levert al 2c/2GB/20.5GB/linux-2.6.
  #
  # Voor andere sizing: maak een aparte template (9001 = larger) ipv per-VM
  # tweaks. Klantelf-bound config in IaC, hardware-shape in template.

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
