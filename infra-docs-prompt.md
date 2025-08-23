You are documenting the entire home & cloud infrastructure. For each component create a separate markdown file named `<component>.md`. Each file must include the following sections:

- **Overview** – brief description of the component and its role.
- **Architecture diagram** – placeholder for a diagram (e.g., an image or mermaid block).
- **Configuration** – relevant configuration snippets (ensure any secrets are redacted).
- **Security considerations** – highlight any risks, especially around secret handling or exposure, and note mitigations.
- **Maintenance checklist** – routine tasks and checks.
- **References** – links to docs, repos, or external resources.

The documentation should describe the *current* state of each component; it is not a compliance audit. Emphasize the home network topology:
- Two subnets behind a NAT.
- **Subnet A** – IPv4‑only.
- **Subnet B** – IPv6‑enabled; hosts receive globally routable IPv6 addresses.
- This allows direct IPv6 communication to resources such as an AWS EC2 instance (free‑tier) that only has a public IPv6 address and no routable IPv4.

**Components to document (one file per component):**
- Cozystack
- DD‑WRT router
- Mikrotik router
- Pi‑hole
- Synology NAS
- Docker Matchbox & dnsmasq
- Pull‑through registry cache
- Fileserver
- PostgreSQL on Neon
- AWS production environment
- AWS sandbox environment
- Terraform for AWS accounts
- Obsidian vault
- GitHub repositories
- Chrome bookmarks
- Social media accounts

**Example commit message for each file:**
`Add <component> documentation – initial draft`
