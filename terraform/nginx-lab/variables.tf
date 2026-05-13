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
  description = "Map of nginx-lab VMs to create on Proxmox"
  type = map(object({
    vm_id  = number
    ip     = string
    memory = number
    cores  = number
    disk   = number
  }))
  default = {
    nginx-lab-clean = {
      vm_id  = 105
      ip     = "192.168.178.55"
      memory = 4096
      cores  = 2
      disk   = 20
    }
    nginx-lab-broken = {
      vm_id  = 106
      ip     = "192.168.178.56"
      memory = 4096
      cores  = 2
      disk   = 20
    }
  }
}
