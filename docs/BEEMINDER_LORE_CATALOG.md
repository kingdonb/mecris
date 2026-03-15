# Beeminder "Lore" Catalog: doc.bmndr.com

This catalog tracks important documentation slugs found in the `doc.beeminder.com` (alias `doc.bmndr.com`) ecosystem. These documents are rendered from Etherpads via the **ExPost** system and represent the philosophical and technical underpinnings of Beeminder.

## 🔗 Core Links & Slugs

### 1. `/priority`
- **Topic:** Background Worker Queues.
- **Lore:** Defines the 5-tier queue system (SNAPPY to UNDULY). Critical for understanding how to balance user-facing responsiveness with heavy background processing.
- **Mecris Impact:** Guided our decision to move toward rate-limited, priority-aware background syncs.

### 2. `/choices`
- **Topic:** Purging unnecessary settings.
- **Lore:** Discusses the philosophy of "Ruthless Purging." Specifically mentions removing the ability to change graph update frequency in Beedroid to simplify the user experience and reduce cognitive load.
- **Mecris Impact:** Reminds us to keep the Android app interface lean—only show what's strictly necessary for the walk/budget status.

### 3. `/slug`
- **Topic:** Goal Naming Philosophy.
- **Lore:** "Nerds care about URLs." Explains why goal slugs are immutable and why they matter more than display titles.
- **Mecris Impact:** Reinforced our focus on using `goal_slug` (e.g., `bike`, `reviewstack`) as the primary identifier across Neon, Beeminder, and Python modules.

### 4. `/beeminder-taglines`
- **Topic:** Branding and Voice.
- **Lore:** A live list of the taglines seen on the homepage. Represents the "Snarky but Supportve" voice of Beeminder.
- **Mecris Impact:** The inspiration for my own professional but sassy personality!

### 5. `/blogo`
- **Topic:** Blog drafting and internal wiki structure.
- **Lore:** General internal wiki documentation.

## 🧠 Architectural Meta-Lore: ExPost
The system itself is a lesson in **Dogfooding**. Instead of using a heavy CMS, they use a tool (Etherpad) that supports real-time collaboration and render it directly. This mirrors our own "Progressive Delivery" approach: we build tools that solve our immediate problems (like the Clozemaster Scraper) and integrate them directly into our daily narrative.
