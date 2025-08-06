#!/usr/bin/env python3
"""
Claude Integration Demo
Demonstrates how Claude would use narrator context to provide contextual assistance
"""

import asyncio
import httpx
import json
import sys
import os
from datetime import datetime, time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class ClaudeNarratorDemo:
    """Simulate how Claude uses narrator context for decision making"""
    
    def __init__(self):
        self.server_url = "http://localhost:8000"
        self.context = None
    
    async def get_narrator_context(self):
        """Fetch current narrator context"""
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{self.server_url}/narrator/context")
            if response.status_code == 200:
                self.context = response.json()
                return True
            return False
    
    def analyze_budget_situation(self):
        """Analyze budget constraints for decision making"""
        if not self.context:
            return {"status": "unknown", "guidance": "Context not available"}
        
        budget_status = self.context.get("budget_status", {})
        days_remaining = budget_status.get("days_remaining", 0)
        remaining_budget = budget_status.get("remaining_budget", 0)
        
        analysis = {
            "days_remaining": days_remaining,
            "remaining_budget": remaining_budget,
            "status": "unknown",
            "guidance": "",
            "scope_recommendation": "normal"
        }
        
        if days_remaining < -2:
            analysis["status"] = "severely_exceeded"
            analysis["guidance"] = "Budget severely exceeded. Only critical fixes and urgent matters."
            analysis["scope_recommendation"] = "emergency_only"
        elif days_remaining < 0:
            analysis["status"] = "exceeded"
            analysis["guidance"] = "Budget exceeded. Focus on wrapping up and high-value work only."
            analysis["scope_recommendation"] = "high_value_only"
        elif days_remaining < 1:
            analysis["status"] = "critical"
            analysis["guidance"] = "Less than 1 day of budget left. Prioritize completion over exploration."
            analysis["scope_recommendation"] = "completion_focused"
        elif days_remaining < 2:
            analysis["status"] = "warning"
            analysis["guidance"] = "Limited budget remaining. Choose tasks carefully."
            analysis["scope_recommendation"] = "selective"
        else:
            analysis["status"] = "healthy"
            analysis["guidance"] = "Sufficient budget for normal operations."
            analysis["scope_recommendation"] = "normal"
        
        return analysis
    
    def analyze_urgency(self):
        """Analyze urgent items and priorities"""
        if not self.context:
            return {"urgent_count": 0, "items": [], "priority_level": "normal"}
        
        urgent_items = self.context.get("urgent_items", [])
        beeminder_alerts = self.context.get("beeminder_alerts", [])
        
        analysis = {
            "urgent_count": len(urgent_items),
            "items": urgent_items,
            "beeminder_alerts": len(beeminder_alerts),
            "priority_level": "normal"
        }
        
        if len(urgent_items) > 2:
            analysis["priority_level"] = "high"
        elif len(urgent_items) > 0:
            analysis["priority_level"] = "elevated"
        
        # Check for specific urgent patterns
        for item in urgent_items:
            if "DERAILING" in item:
                analysis["priority_level"] = "critical"
                break
            elif "BUDGET CRITICAL" in item:
                analysis["priority_level"] = "high"
        
        return analysis
    
    def analyze_walk_status(self):
        """Check if walk reminder is needed"""
        if not self.context:
            return {"needed": False, "message": ""}
        
        walk_status = self.context.get("daily_walk_status", {})
        current_hour = datetime.now().hour
        
        analysis = {
            "needed": False,
            "message": "",
            "goal_slug": walk_status.get("goal_slug", "unknown"),
            "has_activity": walk_status.get("has_activity_today", False)
        }
        
        if (walk_status.get("status") == "needed" and 
            current_hour >= 14 and  # After 2 PM
            not walk_status.get("has_activity_today", False)):
            
            analysis["needed"] = True
            analysis["message"] = "🚶‍♂️ Time for a walk! No activity logged today for bike goal."
        
        return analysis
    
    def generate_claude_response(self, user_request):
        """Generate a Claude response informed by narrator context"""
        if not self.context:
            return {
                "response": "I don't have access to your current context. Let me help as best I can.",
                "context_used": False
            }
        
        budget_analysis = self.analyze_budget_situation()
        urgency_analysis = self.analyze_urgency()
        walk_analysis = self.analyze_walk_status()
        
        # Build context-aware response
        response_parts = []
        
        # Budget-aware scoping
        if budget_analysis["status"] in ["exceeded", "severely_exceeded"]:
            response_parts.append(
                f"⚠️ I notice your Claude budget is {budget_analysis['status']}. "
                f"{budget_analysis['guidance']} I'll keep my response focused and concise."
            )
        elif budget_analysis["status"] == "critical":
            response_parts.append(
                f"⏰ You have less than 1 day of Claude budget remaining. "
                f"I'll prioritize actionable guidance."
            )
        
        # Urgency awareness
        if urgency_analysis["urgent_count"] > 0:
            urgent_list = "\\n".join([f"  • {item}" for item in urgency_analysis["items"]])
            response_parts.append(
                f"🚨 I see {urgency_analysis['urgent_count']} urgent item(s):\\n{urgent_list}\\n"
                f"Should we address these first before working on '{user_request}'?"
            )
        
        # Walk reminder
        if walk_analysis["needed"]:
            response_parts.append(walk_analysis["message"])
        
        # Main response (would be task-specific in real usage)
        response_parts.append(f"Regarding '{user_request}': ")
        
        if budget_analysis["scope_recommendation"] == "emergency_only":
            response_parts.append("Given budget constraints, I'd recommend only pursuing this if it's critical.")
        elif budget_analysis["scope_recommendation"] == "high_value_only":
            response_parts.append("With limited budget, let's focus on the highest-value aspects.")
        elif budget_analysis["scope_recommendation"] == "completion_focused":
            response_parts.append("Let's prioritize completing existing work over starting new tasks.")
        else:
            response_parts.append("I can help you with this task.")
        
        return {
            "response": "\\n\\n".join(response_parts),
            "context_used": True,
            "budget_status": budget_analysis["status"],
            "urgent_items": urgency_analysis["urgent_count"],
            "walk_needed": walk_analysis["needed"]
        }


async def demo_claude_integration():
    """Demonstrate Claude integration with narrator context"""
    print("🧠 Claude-Narrator Integration Demo")
    print("=" * 50)
    
    claude = ClaudeNarratorDemo()
    
    # Get context
    print("📡 Fetching narrator context...")
    success = await claude.get_narrator_context()
    
    if not success:
        print("❌ Failed to get narrator context")
        return False
    
    print("✅ Context retrieved successfully")
    print()
    
    # Demonstrate different scenarios
    scenarios = [
        "I want to implement a new feature for the app",
        "Can you help me debug this complex issue?",
        "Should I refactor this codebase?",
        "Let's work on documentation",
        "I need help with a quick fix"
    ]
    
    print("🎭 Testing Different User Request Scenarios")
    print("-" * 30)
    
    for i, scenario in enumerate(scenarios, 1):
        print(f"\\n{i}. User Request: \"{scenario}\"")
        print(f"   Claude Response:")
        
        claude_response = claude.generate_claude_response(scenario)
        
        # Print the response with proper formatting
        response_lines = claude_response["response"].split("\\n")
        for line in response_lines:
            if line.strip():
                print(f"   {line}")
        
        print(f"\\n   📊 Context Used: {claude_response['context_used']}")
        print(f"   💰 Budget Status: {claude_response['budget_status']}")
        print(f"   🚨 Urgent Items: {claude_response['urgent_items']}")
        print(f"   🚶‍♂️ Walk Needed: {claude_response['walk_needed']}")
        print(f"   {'-' * 40}")
    
    # Show raw context analysis
    print("\\n🔍 Raw Context Analysis")
    print("-" * 25)
    
    budget_analysis = claude.analyze_budget_situation()
    urgency_analysis = claude.analyze_urgency()
    walk_analysis = claude.analyze_walk_status()
    
    print(f"Budget Analysis:")
    print(f"  Status: {budget_analysis['status']}")
    print(f"  Days Remaining: {budget_analysis['days_remaining']}")
    print(f"  Remaining Budget: ${budget_analysis['remaining_budget']:.2f}")
    print(f"  Guidance: {budget_analysis['guidance']}")
    
    print(f"\\nUrgency Analysis:")
    print(f"  Priority Level: {urgency_analysis['priority_level']}")
    print(f"  Urgent Items: {urgency_analysis['urgent_count']}")
    for item in urgency_analysis['items']:
        print(f"    • {item}")
    
    print(f"\\nWalk Analysis:")
    print(f"  Walk Needed: {walk_analysis['needed']}")
    print(f"  Has Activity Today: {walk_analysis['has_activity']}")
    if walk_analysis['message']:
        print(f"  Message: {walk_analysis['message']}")
    
    return True


async def demo_real_time_decision():
    """Demonstrate real-time decision making"""
    print("\\n⚡ Real-Time Decision Making Demo")
    print("=" * 40)
    
    claude = ClaudeNarratorDemo()
    await claude.get_narrator_context()
    
    # Simulate a decision-making scenario
    current_time = datetime.now()
    print(f"Current Time: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Check if this is a good time for different types of work
    decisions = {
        "Complex debugging session": claude.analyze_budget_situation()["scope_recommendation"] in ["normal", "selective"],
        "Quick bug fix": True,  # Always okay for quick fixes
        "New feature development": claude.analyze_budget_situation()["scope_recommendation"] == "normal",
        "Code review": claude.analyze_budget_situation()["scope_recommendation"] in ["normal", "selective", "completion_focused"],
        "Documentation work": claude.analyze_budget_situation()["scope_recommendation"] != "emergency_only",
        "Take a walk": claude.analyze_walk_status()["needed"]
    }
    
    print("\\n🤔 Current Recommendations:")
    for activity, recommended in decisions.items():
        emoji = "✅" if recommended else "❌"
        print(f"   {emoji} {activity}")
    
    return True


async def main():
    """Run the Claude integration demo"""
    success1 = await demo_claude_integration()
    success2 = await demo_real_time_decision()
    
    print("\\n" + "=" * 50)
    
    if success1 and success2:
        print("🎉 Claude-Narrator Integration Demo Complete!")
        print("\\n🧠 Key Benefits Demonstrated:")
        print("   • Context-aware response scoping based on budget")
        print("   • Automatic prioritization of urgent items")
        print("   • Proactive health reminders (walk notifications)")
        print("   • Real-time decision making for different work types")
        print("   • Budget-conscious task recommendations")
        print("\\n✨ The narrator context successfully enables Claude to:")
        print("   - Make smarter recommendations based on your situation")
        print("   - Respect budget constraints automatically")
        print("   - Integrate accountability goals into conversations")
        print("   - Provide personalized, context-aware assistance")
    else:
        print("⚠️ Demo encountered some issues")
    
    return success1 and success2


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)