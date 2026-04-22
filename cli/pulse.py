"""
cli/pulse.py — High-density terminal dashboard for Mecris ecosystem state.

Displays goal runways, budget status, system heartbeats, walk status,
and top recommendations in a single rich-formatted view.

Usage: mecris pulse [--user-id <id>]
"""
import asyncio
from datetime import datetime
from typing import Any, Dict


def _risk_color(risk: str) -> str:
    """Map derail_risk string to a rich color tag."""
    mapping = {
        "CRITICAL": "bold red",
        "WARNING": "bold yellow",
        "CAUTION": "yellow",
        "SAFE": "green",
    }
    return mapping.get(str(risk).upper(), "white")


def _budget_color(pct_used: float) -> str:
    if pct_used >= 0.90:
        return "bold red"
    if pct_used >= 0.75:
        return "bold yellow"
    return "green"


def _walk_status_text(walk_status: Dict[str, Any]) -> tuple[str, str]:
    """Return (label, color) for walk status."""
    status = walk_status.get("status", "unknown")
    if status == "complete":
        return "Complete", "green"
    if status == "needed":
        return "NEEDED", "bold red"
    return status.capitalize(), "white"


def render_pulse(context: Dict[str, Any]) -> None:
    """Render the full pulse dashboard using rich."""
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.columns import Columns
    from rich import box

    console = Console()

    last_updated = context.get("last_updated", "unknown")
    vacation_mode = context.get("vacation_mode", False)
    summary = context.get("summary", "")
    urgent_items = context.get("urgent_items", [])
    recommendations = context.get("recommendations", [])
    goal_runway = context.get("goal_runway", [])
    budget_status = context.get("budget_status", {})
    daily_walk = context.get("daily_walk_status", {})
    system_pulse = context.get("system_pulse", {})
    daily_agg = context.get("daily_aggregate_status", {})

    console.print()
    console.rule(f"[bold cyan]mecris pulse[/bold cyan]  [dim]{last_updated}[/dim]")

    # ── Goal Runway Table ─────────────────────────────────────────────────────
    if goal_runway:
        tbl = Table(title="Goal Runways", box=box.SIMPLE_HEAVY, expand=True)
        tbl.add_column("Slug", style="bold", no_wrap=True)
        tbl.add_column("Safebuf", justify="right")
        tbl.add_column("Risk", justify="center")
        for goal in goal_runway:
            slug = goal.get("slug", "?")
            safebuf = goal.get("safebuf", "?")
            risk = goal.get("derail_risk", "UNKNOWN")
            color = _risk_color(risk)
            tbl.add_row(
                slug,
                str(safebuf),
                f"[{color}]{risk}[/{color}]",
            )
        console.print(tbl)

    # ── Budget + Walk + System panels ─────────────────────────────────────────
    panels = []

    # Budget panel
    remaining = budget_status.get("remaining_budget", 0.0)
    total = budget_status.get("total_budget", 1.0)
    days = budget_status.get("days_remaining", 0.0)
    pct_used = 1.0 - (remaining / total) if total else 0.0
    b_color = _budget_color(pct_used)
    budget_text = (
        f"[{b_color}]${remaining:.2f} remaining[/{b_color}]\n"
        f"{pct_used * 100:.0f}% used  |  {days:.1f} days left"
    )
    panels.append(Panel(budget_text, title="Budget", border_style="cyan"))

    # Walk panel
    walk_label, walk_color = _walk_status_text(daily_walk)
    walk_count = daily_walk.get("steps", daily_walk.get("count", ""))
    walk_extra = f"\n{walk_count} steps" if walk_count else ""
    vacation_tag = "\n[dim]Vacation mode[/dim]" if vacation_mode else ""
    panels.append(Panel(
        f"[{walk_color}]{walk_label}[/{walk_color}]{walk_extra}{vacation_tag}",
        title="Walk Status", border_style="cyan"
    ))

    # System heartbeat panel
    running = system_pulse.get("running", False)
    is_leader = system_pulse.get("is_leader", False)
    pid = system_pulse.get("process_id", "?")
    sched_color = "green" if running else "red"
    leader_tag = " [bold]LEADER[/bold]" if is_leader else ""
    agg_score = daily_agg.get("score", "?")
    agg_all_clear = daily_agg.get("all_clear", False)
    agg_color = "green" if agg_all_clear else "yellow"
    heartbeat_text = (
        f"Scheduler: [{sched_color}]{'UP' if running else 'DOWN'}[/{sched_color}]{leader_tag}\n"
        f"PID: {pid}\n"
        f"Daily goals: [{agg_color}]{agg_score}[/{agg_color}]"
    )
    panels.append(Panel(heartbeat_text, title="Heartbeat", border_style="cyan"))

    console.print(Columns(panels, equal=True))

    # ── Urgent Items ──────────────────────────────────────────────────────────
    if urgent_items:
        console.print()
        console.rule("[bold red]URGENT[/bold red]")
        for item in urgent_items:
            console.print(f"  [bold red]![/bold red] {item}")

    # ── Recommendations ───────────────────────────────────────────────────────
    top_recs = recommendations[:3]
    if top_recs:
        console.print()
        console.rule("[dim]Recommendations[/dim]")
        for rec in top_recs:
            console.print(f"  [cyan]›[/cyan] {rec}")

    console.print()


def build_mock_context() -> Dict[str, Any]:
    """Return a minimal mock context for testing (no MCP calls needed)."""
    return {
        "summary": "Active goals: 2, Pending todos: 5, Beeminder goals: 3, Budget: 4.2 days left",
        "goals_status": {"total": 2},
        "urgent_items": [],
        "beeminder_alerts": [],
        "goal_runway": [
            {"slug": "bike", "safebuf": 5, "derail_risk": "SAFE"},
            {"slug": "weight", "safebuf": 1, "derail_risk": "CRITICAL"},
            {"slug": "greek", "safebuf": 3, "derail_risk": "CAUTION"},
        ],
        "budget_status": {
            "remaining_budget": 12.50,
            "total_budget": 20.0,
            "days_remaining": 4.2,
            "used_budget": 7.50,
        },
        "daily_walk_status": {"status": "needed", "steps": 0},
        "system_pulse": {"running": True, "is_leader": True, "process_id": "mock-pid"},
        "daily_aggregate_status": {"all_clear": False, "score": "1/3"},
        "vacation_mode": False,
        "recommendations": [
            "Address critical Beeminder goals immediately",
            "Priority: Physical Activity Needed!",
        ],
        "last_updated": datetime.now().isoformat(),
    }


async def run_pulse(user_id: str = None) -> None:
    """Fetch live context and render the dashboard."""
    from mcp_server import get_narrator_context
    context = await get_narrator_context(user_id)
    if context.get("error"):
        from rich.console import Console
        Console().print(f"[bold red]Error:[/bold red] {context['error']}")
        return
    render_pulse(context)
