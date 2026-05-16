output "container_id" {
  description = "Proxmox LXC container ID."
  value       = proxmox_virtual_environment_container.agent_lxc.vm_id
}

output "assigned_ip" {
  description = "Static IPv4 assigned to the container."
  value       = var.static_ip
}

output "hostname" {
  description = "Container hostname (= Tailscale hostname)."
  value       = var.hostname
}

output "root_initial_password" {
  description = "Random root password injected at create time. Read once via 'terraform output -raw root_initial_password' if SSH-key recovery is ever needed. Normal access path is SSH-key as the dev user."
  value       = random_password.root.result
  sensitive   = true
}

output "next_steps" {
  description = "What to do after terraform apply succeeds."
  value       = <<-EOT

    LXC ${var.hostname} (id ${var.vm_id}) provisioned at ${var.static_ip}.

    Next steps (from jumpy):

      1. Update ansible/inventory.yml to point ansible_host to ${var.static_ip}
         (use inventory.yml.example as a template).

      2. Mint a Tailscale auth key in the admin console
         (Settings -> Keys -> Generate, reusable=off, ephemeral=off,
          pre-approved=on, tags=tag:homelab-router) and put it in
         ansible/vault/secrets.yml (then ansible-vault encrypt).

      3. Set the vault password file:
           export ANSIBLE_VAULT_PASSWORD_FILE=~/.vault_pass

      4. Run the playbook with verbose logging on this first build:
           cd ../ansible
           ansible-playbook -i inventory.yml playbook.yml -vv \
             2>&1 | tee /tmp/agent-lxc-ansible.log

      5. Once Ansible converges, SSH in and finish two interactive one-offs:
           ssh agent@${var.static_ip}
           claude    # Anthropic account login (browser/copy-paste)
           cat ~/.ssh/id_ed25519_github.pub   # paste into github.com/settings/keys
    EOT
}
