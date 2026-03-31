terraform {
  required_version = ">= 1.0"

  required_providers {
    proxmox = {
      source  = "bpg/proxmox"
      version = "~> 0.69"
    }
  }
}

# Token loaded via TF_VAR_proxmox_api_token (set in .env)
provider "proxmox" {
  endpoint  = "https://192.168.178.10:8006"
  api_token = var.proxmox_api_token
  insecure  = true
}
