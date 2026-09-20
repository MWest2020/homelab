# k8s-cluster — provisioneert de Kubernetes-VM's (3 control-plane + 3 workers) op het
# Proxmox-cluster door per-shape templates te clonen. Data-driven via var.vms (zie tfvars).
# K8s zelf wordt door de Ansible-playbooks geconfigureerd, niet hier.
#
# BEWUST GEEN memory/disk/operating_system blocks (zie feedback_template_per_size):
# de bpg-provider hangt op post-clone hardware-overrides. Shape komt uit de template.
# Enige uitzondering: cpu.type (zie comment bij het cpu-block).

resource "proxmox_virtual_environment_vm" "vm" {
  for_each  = var.vms
  name      = each.key
  node_name = each.value.node_name
  vm_id     = each.value.vm_id
  started   = true

  tags = ["k8s", each.value.role]

  clone {
    vm_id = each.value.template_vm_id
    full  = true
  }

  # Bewuste uitzondering op de no-override-regel hierboven: cpu *type* is een
  # instructieset-vlag, geen hardware-shape (cores/mem/disk). Default
  # x86-64-v2-AES mist AVX2; "host" geeft alle vlaggen van de i7-6700T. Kan
  # veilig omdat alle drie px-hosts identiek zijn en er geen live-migratie is
  # (local-lvm). Pakt pas na volledige stop/start van de VM (reboot in de gast
  # is niet genoeg). Eerst plan + apply -target op één worker (bpg-historie
  # met post-clone overrides, zie feedback_template_per_size).
  # cores HOORT hier, hoe tegenstrijdig dat ook voelt met de regel hierboven.
  # De bpg-provider beheert een gedeclareerd `cpu`-blok in zijn geheel: laat je
  # `cores` weg, dan vult hij de default 1 in en overschrijft hij daarmee de 4
  # cores uit de template. Dat is precies wat er gebeurde — templates 9001/9002
  # (en hun tegenhangers op px-02/03) staan op 4, de zes draaiende VM's stonden
  # op 1, en het cluster liep vol: habitat-runs bleven `Pending` met
  # "0/6 nodes are available: 3 Insufficient cpu" (2026-09-20).
  # Wijzigen pakt pas na een volledige stop/start van de VM, net als cpu.type.
  cpu {
    type  = "host"
    cores = 4
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

output "control_plane_ips" {
  value = { for name, vm in var.vms : name => vm.ip if vm.role == "control-plane" }
}

output "worker_ips" {
  value = { for name, vm in var.vms : name => vm.ip if vm.role == "worker" }
}
