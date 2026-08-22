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
  description = "Map of buzz-relay VMs to create on Proxmox"
  type = map(object({
    vm_id = number
    ip    = string
  }))
  default = {
    buzz-relay = {
      vm_id = 109
      ip    = "192.168.178.60"
    }
  }
}
