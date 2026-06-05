terraform {
  required_version = ">= 1.0"

  required_providers {
    proxmox = {
      source  = "bpg/proxmox"
      version = "~> 0.106.0" # pint 0.106.x; blokkeert 0.107/0.108 (0.108 valt binnen 7-daagse supply-chain-cooldown)
    }
  }
}

# Token loaded via TF_VAR_proxmox_api_token (set in .env)
# Endpoint is een variabele: Fase 0 = laptop (.10, standalone), Fase 2 = een node
# van het 3-node cluster. Token heeft rol TerraformProv over / nodig (incl. VM.Audit).
provider "proxmox" {
  endpoint  = var.proxmox_endpoint
  api_token = var.proxmox_api_token
  insecure  = true
}
