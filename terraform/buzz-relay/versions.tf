terraform {
  required_version = ">= 1.0"

  required_providers {
    proxmox = {
      source  = "bpg/proxmox"
      version = "~> 0.106"
    }
  }
}

# Auth via provider-native env-vars uit .env: PROXMOX_VE_API_TOKEN (+ endpoint/
# insecure staan daar ook, maar hieronder expliciet zodat `plan` zonder .env
# meteen duidelijk faalt op alleen het token).
provider "proxmox" {
  endpoint = "https://192.168.178.10:8006"
  insecure = true
}
