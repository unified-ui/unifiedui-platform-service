#!/bin/sh

INIT_FILE="/vault/file/init.json"
UNSEAL_KEY_FILE="/vault/file/unseal-key"
ROOT_TOKEN_FILE="/vault/file/root-token"

vault server -config=/vault/config/vault-config.hcl &
VAULT_PID=$!

echo "Waiting for Vault to start..."
while true; do
  STATUS=0
  vault status -address="$VAULT_ADDR" > /dev/null 2>&1 || STATUS=$?
  if [ "$STATUS" -ne 1 ]; then
    break
  fi
  sleep 1
done
echo "Vault is up."

if [ ! -f "$UNSEAL_KEY_FILE" ]; then
  echo "Initializing Vault..."
  if vault operator init \
    -address="$VAULT_ADDR" \
    -key-shares=1 \
    -key-threshold=1 \
    -format=json > "$INIT_FILE" 2>&1; then

    grep -A 1 '"unseal_keys_b64"' "$INIT_FILE" | tail -1 | tr -d ' ",[]' > "$UNSEAL_KEY_FILE"
    grep '"root_token"' "$INIT_FILE" | sed 's/.*: *"//;s/".*//' > "$ROOT_TOKEN_FILE"
    echo "Vault initialized. Keys stored."
  else
    echo "ERROR: Vault is already initialized but no local keys found."
    echo "Remove the vault data volume and restart: docker volume rm <vault_volume>"
    kill $VAULT_PID 2>/dev/null
    exit 1
  fi
fi

UNSEAL_KEY=$(cat "$UNSEAL_KEY_FILE")
ROOT_TOKEN=$(cat "$ROOT_TOKEN_FILE")

IS_SEALED=$(vault status -address="$VAULT_ADDR" -format=json 2>/dev/null | grep '"sealed"' | grep -c 'true') || true
if [ "$IS_SEALED" -gt 0 ]; then
  echo "Unsealing Vault..."
  vault operator unseal -address="$VAULT_ADDR" "$UNSEAL_KEY" > /dev/null 2>&1
  echo "Vault unsealed."
fi

export VAULT_TOKEN="$ROOT_TOKEN"

if ! vault token lookup -address="$VAULT_ADDR" admin > /dev/null 2>&1; then
  echo "Creating 'admin' token..."
  vault token create \
    -address="$VAULT_ADDR" \
    -id=admin \
    -policy=root \
    -orphan \
    -display-name="local-dev-admin" \
    -no-default-policy=false > /dev/null 2>&1
  echo "Token 'admin' created."
else
  echo "Token 'admin' already exists."
fi

if ! vault secrets list -address="$VAULT_ADDR" -format=json 2>/dev/null | grep -q '"secret/"'; then
  echo "Enabling KV-v2 secrets engine at secret/..."
  vault secrets enable -address="$VAULT_ADDR" -path=secret kv-v2 > /dev/null 2>&1
  echo "KV-v2 enabled."
else
  echo "KV-v2 at secret/ already enabled."
fi

echo "Vault is ready. (addr=$VAULT_ADDR, token=admin)"
wait $VAULT_PID
