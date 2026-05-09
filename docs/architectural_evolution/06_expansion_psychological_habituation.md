# Area for Expansion 3: The Psychology of Habituation

## The Unexplored Corner
Mecris's core value proposition is accountability. The system employs sophisticated technical mechanisms like the "Nag Ladder" (`services/smart_nag.py`) to enforce behavior. However, the system currently lacks a deep model of human psychological decay.

## Future Research Questions
- **Alarm Fatigue and Habituation:** When a user receives the exact same escalation pattern from Mecris over a 6-month period, psychological habituation guarantees the warnings will lose their efficacy. How does the system algorithmically measure "Nag Decay"?
- **Novelty Injection:** Can the LLM be instructed to mathematically score the semantic similarity of its past 50 reminders and deliberately generate structurally novel, unpredictable interventions to bypass user habituation?
- **Emotional Telemetry:** Currently, telemetry is objective (steps taken, flashcards reviewed). Can the agent use sentiment analysis on the user's chat responses to gauge resentment, frustration, or burnout, and dynamically shift its persona from "Harsh Robot" to "Empathetic Coach"?

*This area bridges the gap between software engineering and behavioral psychology, asking not how to send the message, but how to ensure the message is actually felt.*