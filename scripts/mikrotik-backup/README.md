# MikroTik Configuration Backup & Network Discovery Notes

This directory stores backup data and documentation from the MikroTik router (`hAP ax^2`) investigation regarding cross-subnet communication, client isolation, and roaming between the 13-net and 14-net.

> **Note**: JSON backup dumps containing raw configuration snapshots are ignored by git (`/scripts/mikrotik-backup/*.json`) to avoid committing secrets, credentials, or sensitive network parameters.

---

## 1. Network Discovery & Topology

During the session investigating why the Android app (`com.mecris.go`) on the Pixel 10 Pro encountered timeouts connecting to the local NAS / Pocket-ID endpoint (`https://metnoom.urmanac.com` at `10.17.13.140:443`) when connected to the 13-net:

### Routers & Interfaces Found
- **MikroTik Router (`hAP ax^2`)**:
  - IP Address: `10.17.13.249/24` (on bridge `bridgeLocal`) & `10.17.14.249/24` (on `ether1`).
  - Architecture: `ARM64`, RouterOS `7.24.4 (stable)`.
  - Web / REST API Endpoint: `http://10.17.13.249/rest/`.
  - Bridges:
    - `bridgeLocal` (`D4:01:C3:48:BB:52`) bridging ethernet ports `ether2`–`ether5` and wireless interfaces `mikrotika2` (2.4 GHz) / `mikrotika5` (5 GHz).
  - Subnets:
    - **13-net (`10.17.13.0/24`)**: Local bridge network containing the Synology NAS / PiHole / Pocket-ID at `10.17.13.140`.
    - **14-net (`10.17.14.0/24`)**: Connected via `ether1` (gateway `10.17.14.1`), where developer laptop (`10.17.14.155`) and other hosts reside.
- **Wireless Interfaces (`interface/wifi`)**:
  - `mikrotika2` (`wifi2` default-name): 2.4 GHz AP (`SSID: mikrotika2`, datapath `capdp`).
  - `mikrotika5` (`wifi1` default-name): 5 GHz AP (`SSID: mikrotika5`, datapath `capdp`).

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
   - `/ip/firewall/filter` only contained fasttrack and dummy rules. No inter-client or intra-subnet drop rules existed.
3. **WiFi Datapath & Interface State**:
   - The default datapath `capdp` did not have an explicit `client-isolation` entry configured (in ROS v7, leaving it unpinned can cause ambiguous behavior across updates).
   - In ROS v7 `interface/wifi`, `client-isolation` is governed on the datapath level (`datapath.client-isolation`).

---

## 4. Configuration Changes Applied

To ensure client isolation was explicitly disabled at the WiFi datapath level for both radios:

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

---

## 6. Architecture Roadmap: Splitting Network via WAN & WireGuard

As we split the network across a WAN interface and interconnect via WireGuard:

### 6.1 Current WAN/LAN Interface Layout
- `ether1` currently bridges upstream or connects to `10.17.14.0/24` with IP `10.17.14.249`. Note that `ether1` is in `/interface/bridge/port` as `disabled=true` (defconf WAN behavior).
- When moving `ether1` (or another physical port) to a true WAN role:
  - Ensure the interface is placed in `/interface/list` member `WAN`.
  - Ensure `/ip/firewall/nat` contains masquerade on `out-interface-list=WAN` if NAT is required.
  - Implement standard `/ip/firewall/filter` drop rules on the `input` and `forward` chains for incoming unestablished traffic from `WAN`.

### 6.2 RouterOS v7 WireGuard Implementation Notes
RouterOS 7.x features native kernel WireGuard support. For cross-site or cross-subnet splitting:

1. **WireGuard Interface Setup**:
   ```routeros
   /interface/wireguard/add name=wg0 listen-port=13231 private-key="<GENERATED_PRIVATE_KEY>"
   /ip/address/add address=10.255.0.1/30 interface=wg0 network=10.255.0.0
   ```

2. **Peers & Allowed IPs**:
   ```routeros
   /interface/wireguard/peers/add interface=wg0 public-key="<REMOTE_PUBLIC_KEY>" \
       endpoint-address="<REMOTE_WAN_OR_DDNS>" endpoint-port=13231 \
       allowed-address=10.17.14.0/24,10.255.0.2/32 persistent-keepalive=25s
   ```

3. **Routing Table Entry**:
   ```routeros
   /ip/route/add dst-address=10.17.14.0/24 gateway=wg0
   ```

4. **Firewall Permitting WireGuard**:
   - In `input` chain: Allow UDP port `13231` from the WAN interface list.
   - In `forward` chain: Allow traffic between `bridgeLocal` (`10.17.13.0/24`) and `wg0` (`10.17.14.0/24`), maintaining established/related fasttracking.

5. **Client Roaming & MTU Considerations**:
   - Set WireGuard MTU to `1420` (or `1280` worst-case over PPPoE/cellular) to prevent packet fragmentation for TLS/HTTPS traffic heading to Pocket-ID (`https://metnoom.urmanac.com`) and cloud backends.
   - Add MSS clamping in `/ip/firewall/mangle` if PMTUD issues occur across the WAN tunnel:
     ```routeros
     /ip/firewall/mangle/add chain=forward action=change-mss new-mss=clamp-to-pmtu \
         passthrough=yes protocol=tcp tcp-flags=syn out-interface=wg0
     ```
