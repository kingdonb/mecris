## Claude‑Code‑Man Guide

### Purpose
Provide the instructions needed for Claude‑Code‑Man to generate consistent, developer‑focused documentation for any component of the home & cloud infrastructure.

### Core Prompt (seed for new repo)
```
You are documenting the entire home & cloud infrastructure. For each component create a separate markdown file named `<component>.md`. Each file must include the following sections:
- Overview – brief description of the component and its role.
- Architecture diagram – placeholder for a diagram (e.g., an image or mermaid block).
- Configuration – relevant configuration snippets (ensure any secrets are redacted).
- Security considerations – highlight any risks, especially around secret handling or exposure, and note mitigations.
- Maintenance checklist – routine tasks and checks.
- References – links to docs, repos, or external resources.

Document the *current* state; this is not a compliance audit. Emphasize the home network topology:
- Two subnets behind a NAT.
- Subnet A – IPv4‑only.
- Subnet B – IPv6‑enabled; hosts receive globally routable IPv6 addresses, allowing direct IPv6 communication to resources such as an AWS EC2 free‑tier instance with only a public IPv6 address.

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

**Example commit message:** `Add <component> documentation – initial draft`
```

### Additional Guidance from Conversation
- **Secret handling:** Store all secrets (e.g., Groq API key, Neon Postgres URI, Claude‑code‑proxy token) in `.env` files that are listed in `.gitignore`. Provide an `env.example` with placeholder values for collaborators.
- **LiteLLM + Claude‑code‑proxy deployment:** Use the provided Docker‑Compose setup. Ensure the proxy forwards OpenAI‑compatible requests to LiteLLM, which routes to Groq models using the API key from the environment.
- **Security notes:** Highlight that `.env` files are not committed, rotate keys regularly, and keep container ports minimally exposed.
- **Documentation style:** Keep sections consistent, use markdown headings, and avoid compliance language (no FISMA references).

### Usage
1. Place the core prompt in a file (e.g., `infra_prompt.md`).
2. Run the documentation generator (or manually create files) following the component list.
3. Commit each new `<component>.md` with the example commit message.
4. Update `env.example` when new secrets are added.

This guide equips Claude‑Code‑Man with everything needed to produce accurate, secure, and developer‑oriented documentation for the home lab.
