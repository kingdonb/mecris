# Groq‑Powered Claude Code Summary

## Overview
We now run Claude Code using **Groq**’s token‑as‑a‑service models. Groq provides a set of open‑weight LLMs that are fast, cost‑effective, and well‑suited for code generation and execution.

## Available Models & Key Specs
| Model | Params | Context Window | Max Completion | Token Speed | Modalities |
|---|---|---|---|---|---|
| **OpenAI GPT‑OSS 20B** | 20 B | 128k | 65 536 | ~1 000 tps | Text, code execution |
| **OpenAI GPT‑OSS 120B** | 120 B | 128k | 65 536 | ~500 tps | Text, code execution |
| **llama‑3.1‑8b‑instant** | 8 B | 131 072 | 1 024 | ~1 000 tps | Text, code execution |
| **llama‑3.3‑70b‑versatile** | 70 B | 131 072 | 32 768 | ~500 tps | Text, code execution |
| **meta‑llama/llama‑guard‑4‑12b** | 12 B | 131 072 | 1 024 | ~1 000 tps | Text, code execution |
| **openai/gpt‑oss‑120b** | 120 B | 131 072 | 65 536 | ~500 tps | Text, code execution |
| **openai/gpt‑oss‑20b** | 20 B | 131 072 | 65 536 | ~1 000 tps | Text, code execution |
| **whisper‑large‑v3** | 448 | 100 MB | — | — | Audio transcription |
| **whisper‑large‑v3‑turbo** | 448 | 100 MB | — | — | Audio transcription |

## Pricing (Token‑as‑a‑Service)
| Model | Price per million tokens |
|---|---|
| GPT‑OSS 20B | $0.10 |
| GPT‑OSS 120B | $0.15 |
| Kimi K2 1T | $1.00 |

The **free tier** is not available for these models; the lowest price is $0.10 per million tokens for GPT‑OSS 20B, which translates to roughly **$0.0000001 per token**. For a typical 1 000‑token Claude Code invocation, the cost is around **$0.0001**—well below $0.04.

## Strategic Impact
1. **Cost efficiency** – Using the cheapest available model (GPT‑OSS 20B) keeps per‑invocation cost under one tenth of a cent.
2. **Performance** – Token speeds of 500–1 000 tps mean latency remains well under a second for most requests.
3. **Scalability** – 128k context window allows processing of large codebases without splitting.

## Next Steps
- Update **CLAUDE_API_LIMITATIONS.md** to reflect the new pricing model and the cost per invocation.
- Continue to monitor token usage via the existing budget tracker; adjust thresholds if usage spikes.
- Document the cost savings in the next quarterly budget report.

---
*Prepared by the Mecris narrator*