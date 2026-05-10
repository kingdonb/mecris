# 🌩️ PLAN: IRON TOWN SPIN-UP (t4g Cluster Validation)

**Objective**: Deploy and validate a Talos v1.13.0 / Cozystack v1.3.2 ARM64 cluster on AWS t4g instances to verify the "offramp" images for CM4 hardware.

---

## 🏗️ Phase 1: Custom Image Forging
Instead of a full AMI build, we utilize the Talos Schematic API for rapid iteration.

1. **Generate Schematic ID**:
   - Platform: `aws`
   - Architecture: `arm64`
   - Version: `v1.13.0`
   - Extensions:
     - `siderolabs/tailscale`
     - `siderolabs/iscsi-tools`
     - `siderolabs/util-linux-tools`
     - `urmanac/cozystack-kernel-modules` (latest)
     - `urmanac/spin-extension` (if available, otherwise use `extism` runtime)

2. **Verify URL**: Ensure the image URL `factory.talos.dev/image/<schematic-id>/v1.13.0/aws-arm64.raw.xz` is reachable.

---

## 🚀 Phase 2: Cluster Deployment
Utilize the existing `tools/cozystack-moon-and-back/` infrastructure.

1. **AMI Selection**: Locate the latest official Talos v1.13.0 ARM64 AMI for `eu-west-1`.
2. **Update Launch Script**: Patch `launch-and-configure-talos.sh` with the new AMI ID.
3. **Execution**:
   ```bash
   cd tools/cozystack-moon-and-back
   ./launch-and-configure-talos.sh
   ```
4. **Pivot Upgrade**: Once nodes are online, immediately upgrade them to our custom schematic image:
   ```bash
   talosctl upgrade --image factory.talos.dev/installer/<schematic-id>:v1.13.0
   ```

---

## 🏛️ Phase 3: Cozystack Platform Installation
1. **Bootstrap**: Initialize the Talos cluster using `talm`.
2. **Platform Deployment**: Apply the Cozystack v1.3.2 platform manifests.
3. **Validation**:
   - Verify `linstor` / `drbd` functionality on ARM64.
   - Verify `cilium` / `kube-ovn` networking.
   - Verify `spinkube` (Wasm) execution.

---

## 🐗 Phase 4: The Hand-off
1. **Document Success**: Record the successful Schematic ID and any required machine config patches.
2. **Report to Robert**: Confirm the "Iron Town" validation is complete.
3. **The CM4 Offramp**: Prepare the `.raw` images for burning to Robert's CM4 boards.

---

## 🛑 NON-AGENTIC NOTICE
**To mecris-bot**: This is a human-orchestrated infrastructure plan. You are **NOT** authorized to execute this plan autonomously unless explicitly directed via a GitHub Issue with the label `autonomous-infra`. Observe and record results only.
