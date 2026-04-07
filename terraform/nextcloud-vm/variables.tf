variable "proxmox_api_token" {
  description = "Proxmox API token (terraform@pve!terraform=<uuid>)"
  type        = string
  sensitive   = true
}

variable "vm_gateway" {
  description = "Default gateway for VMs"
  type        = string
  default     = "192.168.178.1"
}

variable "ssh_public_key" {
  description = "SSH public key injected via cloud-init"
  type        = string
  default     = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAID2IyhJJu/28gTKOYR5roiYvBiNjtXlu0HH9liGD3B0f homelab-Goengoeloe-20251030-210553"
}

variable "vms" {
  description = "Map of VMs to create on Proxmox"
  type = map(object({
    vm_id  = number
    ip     = string
    memory = number
    cores  = number
    disk   = number
  }))
  default = {
    proxy = {
      vm_id  = 100
      ip     = "192.168.178.50"
      memory = 1024
      cores  = 1
      disk   = 10
    }
    klant-a = {
      vm_id  = 101
      ip     = "192.168.178.51"
      memory = 4096
      cores  = 2
      disk   = 20
    }
    klant-b = {
      vm_id  = 102
      ip     = "192.168.178.52"
      memory = 4096
      cores  = 2
      disk   = 20
    }
    klant-c = {
      vm_id  = 103
      ip     = "192.168.178.53"
      memory = 4096
      cores  = 2
      disk   = 20
    }
    portainer = {
      vm_id  = 104
      ip     = "192.168.178.54"
      memory = 1024
      cores  = 1
      disk   = 10
    }
  }
}
