terraform {
  required_version = ">= 1.0"

  required_providers {
    proxmox = {
      source  = "bpg/proxmox"
      version = "~> 0.69"
    }
  }
}

# API token loaded from PROXMOX_VE_API_TOKEN env var (source ../../.env)
provider "proxmox" {
  endpoint = "https://192.168.178.10:8006"
  insecure = true
}
