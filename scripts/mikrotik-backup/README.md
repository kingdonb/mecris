# MikroTik Configuration Backup & Network Discovery Notes

This directory stores backup data and documentation from the MikroTik router (`hAP ax^2`) investigation regarding cross-subnet communication, client isolation, and roaming between the 13-net and 14-net.

> **Note**: JSON backup dumps containing raw configuration snapshots are ignored by git (`/scripts/mikrotik-backup/*.json`) to avoid committing secrets, credentials, or sensitive network parameters.

---

## 1. Network Discovery & Topology (As-Is State)

During the investigation into why the Android app (`com.mecris.go`) on the Pixel 10 Pro encountered timeouts connecting to the local NAS / Pocket-ID endpoint (`https://metnoom.urmanac.com` at `10.17.13.140:443`) when connected to the 13-net:

### 1.1 Hardware & System State
- **Device**: MikroTik `hAP ax^2` (`C52iG-5HaxD2HaxD-TC`)
- **Architecture**: `ARM64`, 4 cores, 1 GB RAM
- **RouterOS Version**: `7.24.4 (stable)`
- **REST API Endpoint**: `http://10.17.13.249/rest/`

### 1.2 Interfaces & Layer 2 Bridge
- **`bridgeLocal`** (`D4:01:C3:48:BB:52`):
  - Primary internal bridge serving the **13-net** (`10.17.13.0/24`).
  - Bridge ports: `ether2`, `ether3`, `ether4`, `ether5`, plus wireless interfaces `mikrotika2` and `mikrotika5`.
  - **`ether1`**: Configured as uplink/WAN port, disabled in the bridge (`disabled=true`), connected to the upstream **14-net** (`10.17.14.0/24`).
- **Wireless Interfaces (`interface/wifi`)**:
  - `mikrotika2` (`wifi2` default-name): 2.4 GHz AP (`SSID: mikrotika2`, datapath `capdp`, `mac=D4:01:C3:48:BB:58`).
  - `mikrotika5` (`wifi1` default-name): 5 GHz AP (`SSID: mikrotika5`, datapath `capdp`, `mac=D4:01:C3:48:BB:57`).
  - Security profile: WPA2/WPA3 personal with PSK.

### 1.3 Layer 3 Addressing, Routing & Services
- **IP Addressing (`/ip/address`)**:
  - `10.17.13.249/24` on `bridgeLocal` (comment: `"13net access"`).
  - `10.17.14.249/24` on `ether1` (comment: `"new-wrt net"`).
- **Routing Table (`/ip/route`)**:
  - `0.0.0.0/0` via gateway `10.17.14.1%ether1` (check-gateway: `ping`, distance: `1`).
  - `10.17.13.0/24` directly connected via `bridgeLocal` (distance: `0`).
  - `10.17.14.0/24` directly connected via `ether1` (distance: `0`).
- **DNS Server (`/ip/dns`)**:
  - Primary upstream DNS servers: `10.17.13.140` (Synology NAS / PiHole) and `10.17.12.109`.
- **DHCP Server (`/ip/dhcp-server`)**:
  - Running instance `dhcp2` on `bridgeLocal` serving network `10.17.13.0/24`.
  - Gateway distributed to clients: `10.17.13.249`.
  - DNS distributed to clients: `10.17.13.140` (`domain: urmanac.com`).
  - Dynamic boot / iPXE option configured: `http://10.17.13.251:8080/boot.ipxe`.

---

## 2. Backup Procedure

The router configuration was backed up programmatically over the RouterOS REST API via HTTP using curl and python formatting into this directory:

```bash
BACKUP_DIR="scripts/mikrotik-backup"
mkdir -p "$BACKUP_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

SECTIONS=(
  "interface/bridge"
  "interface/bridge/port"
  "interface/bridge/filter"
  "interface/wifi"
  "interface/wifi/datapath"
  "interface/wifi/security"
  "interface/wifi/configuration"
  "interface/wifi/provisioning"
  "interface/list"
  "interface/list/member"
  "ip/firewall/filter"
  "ip/firewall/nat"
  "ip/address"
  "ip/route"
  "ip/dns"
  "ip/dhcp-server"
  "ip/dhcp-server/network"
  "ip/dhcp-server/lease"
)

for section in "${SECTIONS[@]}"; do
  file_suffix="${section//\//_}_${TIMESTAMP}.json"
  curl -s -u "$CREDS" "http://10.17.13.249/rest/$section" \
    | python3 -m json.tool > "$BACKUP_DIR/$file_suffix" 2>/dev/null
done
```

The resulting backup files were verified before applying any configuration modifications.

---

## 3. Findings from Configuration Analysis

1. **Bridge Horizons & Isolation**:
   - Inspected `/interface/bridge/port`. All ports (`ether1` through `ether5`, plus `mikrotika2` and `mikrotika5`) had `horizon=none` and `auto-isolate=false`.
   - `/interface/bridge/filter` was empty (no Layer 2 filtering or packet dropping).
2. **IP Firewall Rules**:
   - `/ip/firewall/filter` only contained fasttrack (`action=fasttrack-connection`) and passthrough rules. There are no intra-subnet drop or reject rules.
3. **WiFi Datapath & Interface State**:
   - The default datapath `capdp` did not have an explicit `client-isolation` parameter set in RouterOS v7.
   - Without an explicit definition, client-to-client L2 forwarding behavior across wireless-to-bridge ports can vary between ROS minor versions or default bridge offload states.

---

## 4. Configuration Changes Applied

To ensure client isolation is deterministically disabled at the WiFi datapath level for both radios (`mikrotika2` and `mikrotika5`):

```bash
# Explicitly set client-isolation=false on datapath 'capdp' (*1)
curl -s -X PATCH -u "$CREDS" -H "Content-Type: application/json" \
  -d '{"client-isolation":"false"}' \
  "http://10.17.13.249/rest/interface/wifi/datapath/*1"
```

### Verification
A subsequent query to `/interface/wifi/datapath` and `/interface/wifi` confirmed:
- `interface/wifi/datapath/capdp`: `"client-isolation": "false"`
- `interface/wifi/mikrotika2`: `"datapath.client-isolation": "false"`
- `interface/wifi/mikrotika5`: `"datapath.client-isolation": "false"`

---

## 5. Corroborating Client-Side App Improvements

In parallel, `com.mecris.go` was updated with roaming resilience improvements:
- **`PocketIdAuthRepository.loadAuthState`**: Checks the JWT `exp` claim. If still valid according to the token's expiration timestamp, it keeps `AuthState.Authenticated` and initiates a silent background refresh rather than dropping into an error state when moving across subnets where the local identity endpoint may momentarily experience latency or routing handoffs.
- **`PocketIdAuthRepository.refreshAccessTokenSilent`**: Handles transient network/socket exceptions gracefully without downgrading UI auth state.
