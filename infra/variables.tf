variable "subscription_id" {
  type        = string
  description = "Azure subscription id (az account show --query id -o tsv)."
}

variable "location" {
  type    = string
  default = "norwayeast"
}

variable "prefix" {
  type        = string
  default     = "lifeos"
  description = "Name prefix for resources."
}

variable "vm_size" {
  type    = string
  default = "Standard_B2ts_v2"
}

variable "operator_ip" {
  type        = string
  description = "Your current public IP (CIDR /32) allowed to SSH in. e.g. 203.0.113.7/32"
}

variable "ssh_public_key" {
  type        = string
  description = "Contents of your SSH public key (~/.ssh/id_ed25519.pub)."
}

variable "alert_email" {
  type        = string
  description = "Email address that receives monitoring alerts (e.g. VM-down)."
}

variable "ingest_debug_logs" {
  type        = bool
  default     = false
  description = <<-EOT
    Whether DEBUG-level bot logs are sent to Log Analytics (and therefore billed).
    false (default): DEBUG lines are dropped before ingestion — so marking a noisy
    log as DEBUG in the bot stops it from costing anything (it still shows in
    `docker logs` locally). Set true + apply to ingest DEBUG when investigating.
  EOT
}
