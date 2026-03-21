# 📖 The History and Lore of Mecris

## 🕊️ Origins: The Humble MCP Server
Mecris began as a simple **Model Context Protocol (MCP)** server with a **SQLite** backend. Its primary mission was personal: helping its creator maintain focus and accountability on life goals (like walking the dogs, Boris and Fiona) and language learning (Clozemaster).

The original system lived entirely in the local environment, tracking Claude and Gemini usage and calculating budgets in real-time to ensure the "Mecris experiment" remained sustainable on a human-scale budget.

## 🚶‍♂️ The First Evolution: Android & Health Connect
As the need for better data grew, Mecris expanded to Android. A native app was born to bridge the gap between physical activity (tracked via **Google Fit** and **Health Connect**) and the digital accountability system.

This introduced the first distributed challenge: how to sync physical data from a mobile device back to the MCP server without requiring a static public IP for the home lab.

## 🌩️ The Cloud Leap: Spin and Neon
To solve the connectivity gap, Mecris evolved into a **Serverless** architecture.
- **Spin (Wasm)**: A lightweight, secure backend was deployed to the Fermyon Cloud (and eventually Akamai) to act as a stateless relay and ingestion engine.
- **Neon (Postgres)**: The "brain" moved from local SQLite to a serverless Postgres database, enabling real-time sync from anywhere in the world.

## 🔐 The Security Pivot: Towards Production
In March 2026, the project underwent a critical security audit. It was recognized that while the system was functional, it wasn't yet "zero-trust." The move towards production-readiness focused on:
1.  **JWT Verification**: Moving beyond simple OIDC decoding to full cryptographic signature verification.
2.  **PII Encryption**: Ensuring user tokens (Beeminder, etc.) are encrypted at rest with AES-256-GCM.
3.  **Zero-Trust Multi-Tenancy**: Transitioning from a single-user "hobby" project to a hardened, multi-user accountability platform.

## 🤖 The Persona: Mecris the Robot
Throughout its evolution, Mecris has maintained a professional but "sassy" personality. It is not just a logger; it is a coach. It judges progress because it cares. It nags because the goal is not to have data, but to have a better life.

---
*Mecris remains an experiment in deliberate living. It is a testament to what happens when you decide to let an AI keep you honest.*
