variable "proxmox_api_token" {
  description = "Proxmox API token (terraform@pve!terraform=<uuid>), role TerraformProv over /"
  type        = string
  sensitive   = true
}

variable "proxmox_endpoint" {
  description = "Proxmox API endpoint. Fase 0: laptop (https://192.168.178.10:8006). Fase 2: een clusternode."
  type        = string
  default     = "https://192.168.178.10:8006"
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

# Veilige default: lege map → `terraform apply` maakt niets aan tot je via tfvars opt-int.
#
# BELANGRIJK (zie feedback_template_per_size): hardware-shape (cpu/mem/disk) komt UIT de
# template — NIET via overrides na de clone (bpg loopt daarop vast). Per shape een eigen
# template, gebouwd met qm vóór terraform. `template_vm_id` wijst per VM naar die template.
# Hier dus géén cores/memory/disk: alleen per-VM zaken (id, plaatsing, IP, rol).
variable "vms" {
  description = "Map of Kubernetes VMs to create on Proxmox (hardware komt uit de gekozen template)"
  type = map(object({
    vm_id          = number
    node_name      = string
    ip             = string
    template_vm_id = number # per-shape template: bv. CP=9001 (4c/8GB/50GB), worker=9002 (4c/16GB/50GB)
    role           = string # "control-plane" | "worker"
  }))
  default = {}
}
