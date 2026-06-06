# Mecris MCP Tool Audit (Categorized for Token Efficiency)

## Core Tools (Must always be loaded)
- `get_narrator_context`: Strategic overview.
- `get_daily_aggregate_status`: Daily goal progress.
- `complete_goal`: Mark tasks done.
- `get_budget_status`: Financial/Token budget.
- `ask_mecris`: Search docs/logs.
- `search_bookmarks`: Semantic bookmark search.

## Situational Tools (Load on demand)
- `get_beeminder_status`: Detailed goal risk.
- `send_beeminder_alert`: SMS triggers.
- `get_daily_activity`: Activity check.
- `trigger_language_sync`: Scrape Clozemaster.
- `set_review_pump_lever`: Adjust intensity.
- `get_language_velocity_stats`: Review targets.
- `get_weather_report`: Outdoor activity guidance.
- `enqueue_message`: Scheduler tasks.
- `trigger_reminder_check`: Intelligent reminders.

## Administrative / Rarely Used (Move to "Admin" interface or exclude)
- `delete_user_data`: GDPR removal.
- `export_user_data`: GDPR export.
- `record_usage_session`: Usage tracking.
- `record_claude_code_usage`: CLI tracking.
- `update_budget`: Manual adjustment.
- `record_groq_reading`: Odometer sync.
- `get_system_health`: Health dashboard.
- `get_scheduler_queue`: Job queue view.
- `get_coaching_insight`: Personal coaching.
- `set_notification_prefs`: User settings.
- `get_budget_governor_status`: Routing recommendation.

## Ghost / Internal (Excluded from primary user loop)
- `_record_presence`: Handled automatically.
- `get_groq_context`: Internal narrator data.
- `get_unified_cost_status`: Aggregate spend.
