# VM SSH & Operations — Quick Reference

Commands for connecting to the Azure VM (`vm-lifeos`) and managing the bot container.

| Resource             | Value                            |
| -------------------- | -------------------------------- |
| Resource group       | `rg-lifeos`                      |
| Public IP resource   | `pip-lifeos`                     |
| VM name              | `vm-lifeos`                      |
| SSH user             | `azureuser`                      |
| Compose file (on VM) | `/opt/lifeos/docker-compose.yml` |
| Container name       | `lifeos-bot`                     |

---

## 1. Find the VM's current public IP

The IP can change when the VM is recreated, so look it up before connecting.

**Via Terraform output** (run from `infra/`):

```powershell
terraform output -raw vm_public_ip
```

**Via Azure CLI** (no TF state needed):

```powershell
az network public-ip show -g rg-lifeos -n pip-lifeos --query ipAddress -o tsv
```

Store it in a variable for the steps below:

```powershell
$vmip = az network public-ip show -g rg-lifeos -n pip-lifeos --query ipAddress -o tsv
```

## 2. Find your OWN local public IP

This is your machine's outbound IP — the value that goes into the `operator_ip`
tfvar (`/32` CIDR) so the NSG firewall lets you SSH in. If this changed, SSH will
hang/time out rather than show a host-key error.

```powershell
(Invoke-RestMethod ifconfig.me/ip).Trim()
# or
Invoke-RestMethod https://api.ipify.org
```

## 3. Clean up the stale SSH host key

When the VM IP changes (or a new VM lands on an old IP), SSH aborts with
_"REMOTE HOST IDENTIFICATION HAS CHANGED"_. Remove the cached entry for that host.

`-R` takes the **VM's IP/hostname**, NOT a key file. Never touch
`~/.ssh/id_ed25519` — that's your private key (your identity).

```powershell
ssh-keygen -R $vmip
ssh-keygen -R 20.100.203.120
```

## 4. Connect

```powershell
ssh azureuser@$vmip
```

**Full sequence each time the VM IP changes:**

```powershell
$vmip = az network public-ip show -g rg-lifeos -n pip-lifeos --query ipAddress -o tsv
ssh-keygen -R $vmip
ssh azureuser@$vmip
```

### Quick reference — don't mix these up

| Thing                   | What it is               | Used for                                        |
| ----------------------- | ------------------------ | ----------------------------------------------- |
| `operator_ip`           | **your** local public IP | NSG rule — lets you through the firewall        |
| `ssh-keygen -R <vm-ip>` | the **VM's** public IP   | clears the stale host key so SSH doesn't refuse |
| `~/.ssh/id_ed25519`     | your private key         | your identity — leave it alone                  |

---

## 5. Manage the bot container (run ON the VM)

The compose file lives at `/opt/lifeos/docker-compose.yml` (absolute path — note the
leading slash; `cd opt/` from your home dir will not work).

**Stop the bot** (keeps it defined; `start` brings it back):

```bash
cd /opt/lifeos
sudo docker compose stop
```

or, from anywhere:

```bash
sudo docker compose -f /opt/lifeos/docker-compose.yml stop
```

**Start it again** — two options:

- **`docker compose start`** — just restarts the existing container using the
  `.env` that's already on disk. Fast, but does **not** re-fetch secrets.

  ```bash
  sudo docker compose -f /opt/lifeos/docker-compose.yml start
  ```

- **`bootstrap.sh`** (the init script) — use this when secrets need to come from
  Key Vault again (rotated secrets, or a missing/stale `/opt/lifeos/.env` or
  `secrets/` files). It logs in with the VM's Managed Identity, re-fetches every
  secret from the vault, rebuilds `.env` + the Google secret files, pulls the
  image, and runs `docker compose up -d`. This is the same script cloud-init runs
  at first boot.
  ```bash
  sudo bash /opt/lifeos/bootstrap.sh
  ```

**Check status** (look for `lifeos-bot`, status `Exited` or `Up`):

```bash
sudo docker ps -a
```

**Tear down fully** (stops + removes container/network — a fresh VM rebuild re-runs
cloud-init and recreates it):

```bash
sudo docker compose -f /opt/lifeos/docker-compose.yml down
```

> Note: the container uses `restart: unless-stopped`. An explicit `stop` keeps it
> down, but a `down` is needed to remove it entirely.
