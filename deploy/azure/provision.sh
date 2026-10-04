#!/usr/bin/env bash
# Create the Azure VM the whole stack runs on (pay-as-you-go subscription).
# Run on a machine with Azure CLI logged in (`az login`) or in Azure Cloud Shell:
#
#   deploy/azure/provision.sh
#
# Creates, in one resource group: a network security group (SSH from one
# address, 80/443 from anywhere), a static public IP and an Ubuntu 24.04 VM.
# Nothing else is opened: Postgres, Kafka, MinIO, AI2 and Keycloak admin stay
# inside the VM's Docker network (deploy/compose.prod.yml).
#
# Safe to re-run: existing resources are kept. Delete everything with
#   az group delete --name "$AZ_RESOURCE_GROUP"
#
# Settings (environment variables):
#   AZ_RESOURCE_GROUP     default rg-contract-intelligence
#   AZ_LOCATION           default southeastasia
#   AZ_VM_NAME            default ci-vm
#   AZ_VM_SIZE            default Standard_B4ms (4 vCPU, 16 GiB)
#   AZ_OS_DISK_GB         default 64
#   AZ_ADMIN_USER         default azureuser
#   AZ_SSH_SOURCE         address or CIDR allowed to SSH; default: this machine's public IP
#   AZ_SSH_PUBLIC_KEY     path of a public key; default: az creates/uses ~/.ssh/id_rsa
#   AZ_AUTO_SHUTDOWN_UTC  hhmm in UTC to deallocate every day (1500 = 22:00 in Vietnam); default: never
#   AZ_YES=1              do not ask before creating billable resources
set -euo pipefail

: "${AZ_RESOURCE_GROUP:=rg-contract-intelligence}"
: "${AZ_LOCATION:=southeastasia}"
: "${AZ_VM_NAME:=ci-vm}"
: "${AZ_VM_SIZE:=Standard_B4ms}"
: "${AZ_OS_DISK_GB:=64}"
: "${AZ_ADMIN_USER:=azureuser}"
: "${AZ_SSH_SOURCE:=}"
: "${AZ_SSH_PUBLIC_KEY:=}"
: "${AZ_AUTO_SHUTDOWN_UTC:=}"
: "${AZ_YES:=}"

NSG="$AZ_VM_NAME-nsg"
PUBLIC_IP="$AZ_VM_NAME-ip"

command -v az >/dev/null 2>&1 || { echo "Azure CLI not found: https://learn.microsoft.com/cli/azure/install-azure-cli" >&2; exit 1; }
subscription=$(az account show --query name -o tsv 2>/dev/null) || { echo "not logged in: run 'az login'" >&2; exit 1; }

if [ -z "$AZ_SSH_SOURCE" ]; then
  AZ_SSH_SOURCE="$(curl -fsS https://api.ipify.org)/32"
fi

cat <<PLAN
Subscription   : $subscription
Resource group : $AZ_RESOURCE_GROUP ($AZ_LOCATION)
VM             : $AZ_VM_NAME, $AZ_VM_SIZE, Ubuntu 24.04, ${AZ_OS_DISK_GB} GB Standard SSD
Public IP      : $PUBLIC_IP (static)
Open ports     : 22 from $AZ_SSH_SOURCE; 80, 443 from anywhere
Auto-shutdown  : ${AZ_AUTO_SHUTDOWN_UTC:-never}
These resources are billed while they exist (the VM per second while running).
PLAN
if [ -z "$AZ_YES" ]; then
  read -r -p "Create them? [y/N] " answer
  [ "$answer" = y ] || [ "$answer" = Y ] || { echo "nothing created"; exit 1; }
fi

echo "[azure] resource group"
az group create --name "$AZ_RESOURCE_GROUP" --location "$AZ_LOCATION" --output none

echo "[azure] network security group"
az network nsg create --resource-group "$AZ_RESOURCE_GROUP" --name "$NSG" --output none
rule() {  # name priority protocol port source
  az network nsg rule create --resource-group "$AZ_RESOURCE_GROUP" --nsg-name "$NSG" \
    --name "$1" --priority "$2" --direction Inbound --access Allow --protocol "$3" \
    --destination-port-ranges "$4" --source-address-prefixes "$5" --output none
}
rule allow-ssh 1000 Tcp 22 "$AZ_SSH_SOURCE"
rule allow-http 1010 Tcp 80 Internet    # Let's Encrypt HTTP-01 and the redirect to HTTPS
rule allow-https 1020 Tcp 443 Internet
rule allow-http3 1030 Udp 443 Internet

echo "[azure] static public IP"
az network public-ip create --resource-group "$AZ_RESOURCE_GROUP" --name "$PUBLIC_IP" \
  --sku Standard --allocation-method Static --version IPv4 --output none

if az vm show --resource-group "$AZ_RESOURCE_GROUP" --name "$AZ_VM_NAME" --output none 2>/dev/null; then
  echo "[azure] VM $AZ_VM_NAME exists, not touching it"
else
  echo "[azure] VM (a few minutes)"
  if [ -n "$AZ_SSH_PUBLIC_KEY" ]; then
    ssh_args=(--ssh-key-values "$AZ_SSH_PUBLIC_KEY")
  else
    ssh_args=(--generate-ssh-keys)
  fi
  az vm create --resource-group "$AZ_RESOURCE_GROUP" --name "$AZ_VM_NAME" \
    --image Ubuntu2404 --size "$AZ_VM_SIZE" \
    --admin-username "$AZ_ADMIN_USER" "${ssh_args[@]}" \
    --os-disk-size-gb "$AZ_OS_DISK_GB" --storage-sku StandardSSD_LRS \
    --public-ip-address "$PUBLIC_IP" --nsg "$NSG" --output none
fi

if [ -n "$AZ_AUTO_SHUTDOWN_UTC" ]; then
  echo "[azure] auto-shutdown at $AZ_AUTO_SHUTDOWN_UTC UTC"
  az vm auto-shutdown --resource-group "$AZ_RESOURCE_GROUP" --name "$AZ_VM_NAME" \
    --time "$AZ_AUTO_SHUTDOWN_UTC" --output none
fi

ip=$(az network public-ip show --resource-group "$AZ_RESOURCE_GROUP" --name "$PUBLIC_IP" --query ipAddress -o tsv)
dashed=${ip//./-}

cat <<NEXT

[azure] done. Public IP: $ip
  frontend : https://app-$dashed.sslip.io
  API      : https://api-$dashed.sslip.io
  login    : https://auth-$dashed.sslip.io

Next, on the VM (deploy/AZURE.md, step 2):
  ssh $AZ_ADMIN_USER@$ip
  sudo git clone https://github.com/AI20K-VGR/contract-intelligence-core.git /opt/contract-intelligence
  cd /opt/contract-intelligence && sudo git checkout <branch>
  sudo deploy/bootstrap.sh
  sudo nano deploy/.env.prod      # AI2_LLM_BASE_URL, AI2_LLM_API_KEY, SMTP_*
  sudo nano ai-service/.env       # MISTRAL_API_KEY, OPENAI_API_KEY
  sudo deploy/deploy.sh

Stop paying for compute (disk and IP are still billed):
  az vm deallocate --resource-group $AZ_RESOURCE_GROUP --name $AZ_VM_NAME
Start again (same IP, containers restart on their own):
  az vm start --resource-group $AZ_RESOURCE_GROUP --name $AZ_VM_NAME
Delete everything:
  az group delete --name $AZ_RESOURCE_GROUP
NEXT
