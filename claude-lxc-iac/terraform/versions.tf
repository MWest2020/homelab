terraform {
  required_version = ">= 1.0"

  required_providers {
    proxmox = {
      source  = "bpg/proxmox"
      version = "~> 0.106"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}

# Reads token from var.proxmox_api_token (which can come via env
# TF_VAR_proxmox_api_token or PROXMOX_VE_API_TOKEN). Endpoint is also
# overrideable via env PROXMOX_VE_ENDPOINT if you want zero secrets in
# state-affecting files.
provider "proxmox" {
  endpoint  = var.proxmox_api_url
  api_token = var.proxmox_api_token
  insecure  = var.proxmox_insecure
}
