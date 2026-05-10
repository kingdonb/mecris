# 🌩️ PLAN: IRON TOWN SPIN-UP (t4g Cluster Validation)

**Objective**: Deploy and validate a Talos v1.13.0 / Cozystack v1.3.2 ARM64 cluster on AWS t4g instances to verify the "offramp" images for CM4 hardware.

---

## 💰 Phase 0: Cost Analysis & Bastion Pre-Flight

**CRITICAL: Do NOT spin up nodes without acknowledging the cost matrix.**
As of late 2025/2026, the AWS `t4g.small` free tier may have expired or shifted. Furthermore, Cozystack requires a specific networking topology to avoid elastic IP and IPv4 charges.

1. **The Bastion Requirement**:
   - Talos nodes must be placed in a **Private Subnet**.
   - A **Bastion Host** (t4g.nano/small) with a single IPv6/IPv4 address must be deployed in the Public Subnet.
   - **Why?** This prevents paying for 3-4 public IPv4 addresses. The Bastion acts as the Wireguard/Tailscale entry point and hosts the GHCR registry cache (`10.10.1.100:5054`) so private nodes can pull images without a costly NAT Gateway.
2. **Cost Matrix (Per 2-3 Hour Session)**:
   - Compute (3x t4g.small + 1x Bastion): ~$0.15 - $0.30
   - EBS Storage (4x 8GB gp3): ~$0.20 - $0.40
   - NAT Gateway (if used for egress): ~$0.15 - $0.35
   - **Total Estimated Cost per Session**: **$0.50 - $1.05**
3. **The Rule**: If a session is expected to cost >$2.00 or the monthly validation budget exceeds $15, abort the cloud run and wait for the physical CM4 boards.

---

## 🏗️ Phase 1: Custom Image Forging
Instead of a full AMI build (which incurs snapshot storage costs across regions), we utilize the Talos Schematic API for rapid, stateless iteration.

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

1. **Deploy Bastion**: Apply Terraform/scripts to launch the Bastion and configure the local registry cache.
2. **AMI Selection**: Locate the latest official Talos v1.13.0 ARM64 AMI for `eu-west-1`.
3. **Update Launch Script**: Patch `launch-arm64-cluster.sh` with the new AMI ID and ensure it points to the Bastion's registry cache.
4. **Execution**:
   ```bash
   cd tools/cozystack-moon-and-back
   ./launch-arm64-cluster.sh
   ```
5. **Pivot Upgrade**: Once nodes are online (via boot-to-talos), immediately upgrade them to our custom schematic image:
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

## 🐗 Phase 4: The Hand-off & Teardown
1. **Document Success**: Record the successful Schematic ID and any required machine config patches.
2. **Teardown**: Immediately run `./cleanup-all-instances.sh` to halt the AWS billing meter.
3. **Report to Robert**: Confirm the "Iron Town" validation is complete.
4. **The CM4 Offramp**: Prepare the `.raw` images for burning to Robert's CM4 boards.

---

## 🛑 NON-AGENTIC NOTICE
**To mecris-bot**: This is a human-orchestrated infrastructure plan. You are **NOT** authorized to execute this plan autonomously unless explicitly directed via a GitHub Issue with the label `autonomous-infra`. Observe and record results only. Do not spawn EC2 instances.
