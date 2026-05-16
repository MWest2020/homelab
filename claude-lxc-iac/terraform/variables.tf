# --- Proxmox connection ---

variable "proxmox_api_url" {
  description = "Proxmox API endpoint"
  type        = string
  default     = "https://192.168.178.10:8006"
}

variable "proxmox_api_token" {
  description = "Proxmox API token (terraform@pve!automation-lxc=<uuid>). Prefer env: TF_VAR_proxmox_api_token or PROXMOX_VE_API_TOKEN."
  type        = string
  sensitive   = true
}

variable "proxmox_insecure" {
  description = "Skip TLS verification (self-signed cert in homelab)."
  type        = bool
  default     = true
}

variable "node_name" {
  description = "Proxmox node where the LXC lands."
  type        = string
  default     = "proxmox"
}

# --- LXC identity ---

variable "vm_id" {
  description = "LXC container ID. 2xx range reserved for LXCs (VMs live in 1xx)."
  type        = number
  default     = 210
}

variable "hostname" {
  description = "Container hostname (= Tailscale hostname by default in the ansible role)."
  type        = string
  default     = "agent-lxc"
}

# --- Template ---

variable "template_file_id" {
  description = "Pre-downloaded LXC template path on Proxmox. Download once with: pveam download local <name>."
  type        = string
  default     = "local:vztmpl/ubuntu-24.04-standard_24.04-2_amd64.tar.zst"
}

# --- Resources ---

variable "cores" {
  description = "vCPU cores."
  type        = number
  default     = 2
}

variable "memory_mb" {
  description = "RAM in MB."
  type        = number
  default     = 4096
}

variable "swap_mb" {
  description = "Swap in MB."
  type        = number
  default     = 1024
}

variable "rootfs_storage" {
  description = "Storage pool for the container rootfs."
  type        = string
  default     = "local-lvm"
}

variable "rootfs_size_gb" {
  description = "Rootfs size in GB."
  type        = number
  default     = 50
}

# --- Network (REQUIRED, no defaults — fail loudly if missing) ---

variable "static_ip" {
  description = "Static IPv4 for the container on the homelab LAN (e.g. 192.168.178.58). Required — no default to prevent silent DHCP fallback."
  type        = string

  validation {
    condition     = can(regex("^[0-9]+\\.[0-9]+\\.[0-9]+\\.[0-9]+$", var.static_ip))
    error_message = "static_ip must be an IPv4 address (e.g. 192.168.178.58)."
  }
}

variable "gateway" {
  description = "Default IPv4 gateway for the container."
  type        = string
  default     = "192.168.178.1"
}

variable "cidr" {
  description = "CIDR prefix length for the LAN (e.g. 24 for /24)."
  type        = number
  default     = 24
}

variable "bridge" {
  description = "Proxmox bridge for the container NIC."
  type        = string
  default     = "vmbr0"
}

# --- SSH key injection ---

variable "ssh_public_key_path" {
  description = "Path to the SSH public key on the operator workstation that gets injected at create time (used by Ansible to bootstrap as root, then by the dev user after the base role runs)."
  type        = string
  default     = "~/.ssh/id_ed25519_homelab.pub"
}
