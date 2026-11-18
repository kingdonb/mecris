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


_GRANT_COLORS = {"GOOD": "green", "ENDING": "bold yellow", "ENDED": "bold red"}


def _budget_text(budget_status: Dict[str, Any]) -> str:
    """Budget panel body, by source_type (kingdonb/mecris#345)."""
    source_type = budget_status.get("source_type") or "api_credit"
    if source_type == "subscription":
        plan = (budget_status.get("plan") or "subscription").strip()
        plan = plan[:1].upper() + plan[1:]
        health = budget_status.get("budget_health", "unknown")
        color = _GRANT_COLORS.get(health, "white")
        end = budget_status.get("grant_end") or budget_status.get("period_end", "?")
        verb = "ended" if health == "ENDED" else "until"
        return (
            f"[{color}]Claude {plan}[/{color}]\n"
            f"{verb} {end}  |  {budget_status.get('days_to_grant_end', '?')} days left"
        )
    if source_type == "retired":
        return "[dim]retired (no dollar budget)[/dim]"
    if source_type == "helix_grant":  # #393
        used, balance = budget_status.get("used_budget"), budget_status.get("helix_balance")
        if used is None or balance is None:
            return "[dim]Helix grant (wallet unavailable)[/dim]"
        line = (f"[cyan]Helix ${used:.2f} of ${budget_status.get('total_budget', 100):.0f}[/cyan] this period\n"
                f"balance ${balance:.2f}  |  {budget_status.get('days_remaining', '?')} days to the next grant")
        pace, target = budget_status.get("target_pace_per_day"), budget_status.get("target")
        if pace is not None and target:
            line += f"\n${pace:.2f}/day to ${target['balance']:.0f} by {target['date']}"
        return line

    remaining = budget_status.get("remaining_budget", 0.0)
    total = budget_status.get("total_budget", 1.0)
    days = budget_status.get("days_remaining", 0.0)
    pct_used = 1.0 - (remaining / total) if total else 0.0
    b_color = _budget_color(pct_used)
    if budget_status.get("period_expired"):
        days_line = f"[yellow]period ended {budget_status.get('period_end', '?')}[/yellow]"
    else:
        days_line = f"{days:.1f} days left"
    return (
        f"[{b_color}]${remaining:.2f} remaining[/{b_color}]\n"
        f"{pct_used * 100:.0f}% used  |  {days_line}"
    )


def _role_state_text(system_pulse: Dict[str, Any]) -> str:
    """Leader / standby as a state (#346). Standby is normal failover, not an error."""
    state = system_pulse.get("state")
    if state is None:
        state = "leader" if system_pulse.get("is_leader") else "unknown"
    if state == "leader":
        return "[bold]LEADER[/bold]"
    if state == "standby":
        return f"[dim]standby (leader {system_pulse.get('leader_process_id') or 'unknown'})[/dim]"
    return f"[dim]{state}[/dim]"


def _heartbeat_text(system_pulse: Dict[str, Any], daily_agg: Dict[str, Any]) -> str:
    running = system_pulse.get("running", False)
    pid = system_pulse.get("process_id", "?")
    sched_color = "green" if running else "red"
    agg_score = daily_agg.get("score", "?")
    agg_color = "green" if daily_agg.get("all_clear", False) else "yellow"
    lines = [
        f"Scheduler: [{sched_color}]{'UP' if running else 'DOWN'}[/{sched_color}] {_role_state_text(system_pulse)}",
        f"PID: {pid}",
    ]
    if system_pulse.get("last_error"):
        lines.append(f"[red]Error: {system_pulse['last_error']}[/red]")
    lines.append(f"Daily goals: [{agg_color}]{agg_score}[/{agg_color}]")
    return "\n".join(lines)


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
    panels.append(Panel(_budget_text(budget_status), title="Budget", border_style="cyan"))

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
    panels.append(Panel(_heartbeat_text(system_pulse, daily_agg), title="Heartbeat", border_style="cyan"))

    console.print(Columns(panels, equal=True))

    # ── Urgent Items ──────────────────────────────────────────────────────────
    if urgent_items:
        console.print()
        console.rule("[bold red]URGENT[/bold red]")
        for item in urgent_items:
            console.print(f"  [bold red]![/bold red] {item}")

    # ── Recommendations ───────────────────────────────────────────────────────
    top_recs = recommendations[:5]
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
