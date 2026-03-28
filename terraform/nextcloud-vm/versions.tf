terraform {
  required_version = ">= 1.0"

  required_providers {
    proxmox = {
      source  = "bpg/proxmox"
      version = "~> 0.69"
    }
  }
}

# Provider reads credentials from environment variables:
#   PROXMOX_VE_ENDPOINT   — https://192.168.178.10:8006
#   PROXMOX_VE_API_TOKEN  — terraform@pve!terraform=<token>
#   PROXMOX_VE_INSECURE   — true (self-signed cert)
#
# Source these before running terraform:
#   source ../../.env
provider "proxmox" {}
