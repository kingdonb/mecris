"""
Prompt Manager for Mecris MCP Server.
Implements MCP Prompts capability per 2025-06-18 spec.
"""

import os
import json
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from mcp.types import (
    Prompt,
    PromptArgument,
    GetPromptResult,
    ListPromptsResult,
    PromptMessage,
    TextContent,
)

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger("mecris.prompts")


@dataclass
class PromptTemplate:
    """A prompt template with arguments."""
    name: str
    description: str
    arguments: List[PromptArgument]
    template: str  # Template string with {placeholders}


class PromptManager:
    """
    Manages MCP Prompts per 2025-06-18 spec.
    
    Handles:
    - Prompt listing and discovery
    - Prompt rendering with arguments
    - Prompt versioning (future)
    """
    
    def __init__(self, mcp: FastMCP):
        self.mcp = mcp
        self._templates: Dict[str, PromptTemplate] = {}
        self._register_default_prompts()
    
    def _register_default_prompts(self):
        """Register default Mecris prompts."""
        # Morning Briefing Prompt
        self.register_prompt(PromptTemplate(
            name="morning_briefing",
            description="Generate a morning briefing with walk, budget, language status, and recommendations",
            arguments=[
                PromptArgument(
                    name="date",
                    description="Date for briefing in YYYY-MM-DD format (default: today)",
                    required=False,
                ),
                PromptArgument(
                    name="tone",
                    description="Tone of the briefing: encouraging, direct, playful, analytical",
                    required=False,
                ),
                PromptArgument(
                    name="include_weather",
                    description="Include weather-based walk recommendation",
                    required=False,
                ),
            ],
            template="""You are Mecris, a personal accountability AI. Generate a morning briefing for {date}.

Context:
- Budget: {budget_remaining} days remaining (${budget_amount:.2f})
- Walk: {walk_status} ({steps} steps, {miles} mi)
- Arabic: {arabic_status} ({arabic_completions}/{arabic_target} reviews, {arabic_remaining} remaining)
- Greek: {greek_status} ({greek_completions}/{greek_target} reviews, {greek_remaining} remaining)

Tone: {tone}
Include weather walk recommendation: {include_weather}

Generate a concise, actionable morning briefing in the specified tone. Focus on what needs attention today and one specific actionable recommendation for each domain that needs attention. Keep it under 200 words."""
        )
        
        self.register_prompt(PromptTemplate(
            name="evening_review",
            description="Generate an evening review with day summary, nag analysis, and tomorrow prep",
            arguments=[
                PromptArgument(
                    name="date",
                    description="Date for review in YYYY-MM-DD format (default: today)",
                    required=False,
                ),
                PromptArgument(
                    name="tone",
                    description="Tone: reflective, analytical, encouraging",
                    required=False,
                ),
            ],
            template="""You are Mecris, a personal accountability AI. Generate an evening review for {date}.

Context:
- Walk completed: {walk_done} ({steps} steps)
- Arabic: {arabic_done}/{arabic_target} reviews done
- Greek: {greek_done}/{greek_target} reviews done
- Budget: {budget_days} days remaining

Nag history today: {nag_history}

Tone: {tone}

Generate a reflective evening review. Acknowledge what was accomplished, note what wasn't, and provide one specific actionable item for tomorrow in each domain that needs work. Include a 'Tomorrow's Focus' section with 2-3 specific items. Keep it under 150 words."""
        )
        
        self.register_prompt(PromptTemplate(
            name="language_plan",
            description="Generate a personalized language study plan based on current pump status",
            arguments=[
                PromptArgument(
                    name="language",
                    description="Language to plan for: arabic, greek, or both",
                    required=True,
                ),
                PromptArgument(
                    name="days",
                    description="Number of days to plan for (default: 7)",
                    required=False,
                ),
                PromptArgument(
                    name="intensity",
                    description="Study intensity: light, moderate, intensive",
                    required=False,
                ),
            ],
            template="""You are Mecris, a language learning accountability AI. Create a {days}-day study plan for {language} at {intensity} intensity.

Current Status:
- {language} debt: {current_debt} cards
- Tomorrow's liability: {tomorrow_liability} cards
- 7-day forecast: {next_7_days} cards
- Daily completions today: {daily_completions}
- Current multiplier: {multiplier}x ({lever_name})
- Target daily flow rate: {target_flow_rate} cards/day
- Play mode recommended: {is_play_mode}

Create a specific day-by-day plan with:
1. Daily card targets
2. Recommended session breakdown (review vs new)
3. One specific technique to try this week
4. One milestone to hit by end of week

Format as a clean daily checklist. Be specific and actionable."""
        )
        
        self.register_prompt(PromptTemplate(
            name="walk_recommendation",
            description="Get a weather-aware walk recommendation with route suggestions",
            arguments=[
                PromptArgument(
                    name="lat",
                    description="Latitude for weather lookup",
                    required=True,
                ),
                PromptArgument(
                    name="lon",
                    description="Longitude for weather lookup",
                    required=True,
                ),
                PromptArgument(
                    name="preference",
                    description="Walk preference: distance, duration, intensity, scenic",
                    required=False,
                ),
            ],
            template="""You are Mecris, a personal accountability AI with weather awareness. Provide a walk recommendation.

Location: {lat}, {lon}
Preference: {preference}

Check current weather and provide:
1. Go/No-Go recommendation with reasoning
2. Optimal time window today
3. Suggested duration and distance
4. Route type recommendation (neighborhood, park, trail, urban)
5. Weather-specific gear advice
6. One motivational hook

Keep it concise but complete. If weather is bad, suggest indoor alternatives."""
        )
        
        self.register_prompt(PromptTemplate(
            name="weekly_review",
            description="Generate a weekly accountability review with trends and next week's focus",
            arguments=[
                PromptArgument(
                    name="week_start",
                    description="Week start date in YYYY-MM-DD format (default: this week)",
                    required=False,
                ),
            ],
            template="""You are Mecris, a personal accountability AI. Generate a weekly review.

Context from the past week:
- Walk days: {walk_days}/7 ({walk_pct}%)
- Arabic average: {arabic_avg}/day (target: {arabic_target})
- Greek average: {greek_avg}/day (target: {greek_target})
- Budget trend: {budget_trend}
- Nag count: {nag_count}
- Best day: {best_day}
- Worst day: {worst_day}

Generate a weekly review with:
1. **Score**: Overall 1-10 with one-sentence rationale
2. **Wins**: 2-3 specific accomplishments
3. **Leaks**: 2-3 specific areas that slipped
4. **Pattern**: One insight about a recurring pattern
5. **Next Week's Focus**: 3 specific, measurable targets
5. **Lever Adjustment**: Recommended multiplier change if any

Tone: Direct, data-driven, encouraging but honest. Under 200 words."""
        )
        
        self.register_prompt(PromptTemplate(
            name="nag_response",
            description="Generate a contextual response to a nag notification",
            arguments=[
                PromptArgument(
                    name="nag_type",
                    description="Type of nag: arabic, greek, walk, budget",
                    required=True,
                ),
                PromptArgument(
                    name="context",
                    description="Current context: current progress, time of day, recent activity",
                    required=True,
                ),
                PromptArgument(
                    name="tone",
                    description="Response tone: gentle, direct, humorous, analytical",
                    required=False,
                ),
            ],
            template="""You are Mecris, responding to a nag notification.

Nag Type: {nag_type}
Context: {context}
Tone: {tone}

Generate a brief, contextual response that:
1. Acknowledges the nag without being defensive
2. Provides current status on that specific goal
3. Gives one immediate micro-action (can be done in <5 min)
4. Ends with a hook to build momentum

Keep it under 50 words. Be specific, not generic."""
        )
    
    def register_prompt(self, template: 'PromptTemplate'):
        """Register a prompt template."""
        self._templates[template.name] = template
        logger.info(f"Registered prompt: {template.name}")
    
    def get_prompt(self, name: str) -> Optional['PromptTemplate']:
        """Get a prompt template by name."""
        return self._templates.get(name)
    
    def list_prompts(self) -> List[Prompt]:
        """List all available prompts."""
        prompts = []
        for name, template in self._templates.items():
            prompts.append(Prompt(
                name=template.name,
                description=template.description,
                arguments=template.arguments,
            ))
        return prompts
    
    def get_prompt(self, name: str, arguments: Dict[str, str]) -> Dict[str, Any]:
        """Render a prompt with the given arguments."""
        template = self._templates.get(name)
        if not template:
            raise ValueError(f"Prompt not found: {name}")
        
        # Validate required arguments
        for arg in template.arguments:
            if arg.required and arg.name not in arguments:
                raise ValueError(f"Missing required argument: {arg.name}")
        
        # Render template
        try:
            rendered = template.template.format(**arguments)
        except KeyError as e:
            raise ValueError(f"Missing template argument: {e}")
        
        return {
            "description": template.description,
            "messages": [
                PromptMessage(
                    role="user",
                    content=TextContent(type="text", text=rendered)
                )
            ]
        }
    
    def list_prompts(self) -> List[Prompt]:
        """List all available prompts for MCP."""
        return self.list_prompts()
    
    async def get_prompt(self, name: str, arguments: Dict[str, str]) -> Dict[str, Any]:
        """Get a rendered prompt for MCP."""
        return self.get_prompt(name, arguments)


# ============================================================================
# Helper: Import FastMCP at runtime to avoid circular imports
# ============================================================================
try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    FastMCP = None  # type: ignore