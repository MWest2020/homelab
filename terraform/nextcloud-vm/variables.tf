variable "proxmox_api_token" {
  description = "Proxmox API token (terraform@pve!terraform=<uuid>)"
  type        = string
  sensitive   = true
}

variable "vm_ip" {
  description = "Static IP for the Nextcloud VM (CIDR notation)"
  type        = string
  default     = "192.168.178.50/24"
}

variable "vm_gateway" {
  description = "Default gateway for the Nextcloud VM"
  type        = string
  default     = "192.168.178.1"
}

variable "ssh_public_key" {
  description = "SSH public key injected via cloud-init"
  type        = string
  default     = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAID2IyhJJu/28gTKOYR5roiYvBiNjtXlu0HH9liGD3B0f homelab-Goengoeloe-20251030-210553"
}
