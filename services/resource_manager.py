"""
Resource Manager for Mecris MCP Server.
Implements MCP Resources capability per 2025-06-18 spec.
"""

import os
import json
import asyncio
from datetime import datetime, date, timezone
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass, field
from urllib.parse import urlparse

from mcp.types import (
    Resource,
    ResourceTemplate,
    ListResourcesResult,
    ReadResourceResult,
    ResourceContents,
    TextResourceContents,
    BlobResourceContents,
)

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger("mecris.resources")


@dataclass
class ResourceSubscription:
    """Tracks a client's subscription to a resource."""
    uri: str
    client_id: str
    subscribed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class ResourceManager:
    """
    Manages MCP Resources per 2025-06-18 spec.
    
    Handles:
    - Resource listing and discovery
    - Resource reading (text and blob)
    - Resource templates (URI templates with variables)
    - Subscriptions and notifications
    """
    
    def __init__(self, mcp: FastMCP):
        self.mcp = mcp
        self._subscriptions: Dict[str, Set[str]] = {}  # uri -> set of client_ids
        self._client_subscriptions: Dict[str, Set[str]] = {}  # client_id -> set of uris
        self._resource_cache: Dict[str, Any] = {}
        self._notification_callbacks: List[callable] = []
        
        # Register MCP resource handlers
        self._register_handlers()
    
    def _register_handlers(self):
        """Register MCP resource handlers with FastMCP."""
        # Note: FastMCP doesn't have built-in resource handlers yet
        # We'll use the low-level MCP protocol handlers
        pass
    
    def add_notification_callback(self, callback: callable):
        """Add a callback for resource change notifications."""
        self._notification_callbacks.append(callback)
    
    def remove_notification_callback(self, callback: callable):
        """Remove a notification callback."""
        if callback in self._notification_callbacks:
            self._notification_callbacks.remove(callback)
    
    async def notify_resource_changed(self, uri: str):
        """Notify all subscribers that a resource has changed."""
        subscribers = self._subscriptions.get(uri, set())
        if not subscribers:
            return
        
        logger.info(f"Notifying {len(subscribers)} subscribers of change to {uri}")
        
        for callback in self._notification_callbacks:
            try:
                await callback(uri, subscribers)
            except Exception as e:
                logger.error(f"Notification callback failed: {e}")
    
    def subscribe(self, uri: str, client_id: str) -> bool:
        """Subscribe a client to a resource URI."""
        if uri not in self._subscriptions:
            self._subscriptions[uri] = set()
        self._subscriptions[uri].add(client_id)
        
        if client_id not in self._client_subscriptions:
            self._client_subscriptions[client_id] = set()
        self._client_subscriptions[client_id].add(uri)
        
        logger.info(f"Client {client_id} subscribed to {uri}")
        return True
    
    def unsubscribe(self, uri: str, client_id: str) -> bool:
        """Unsubscribe a client from a resource URI."""
        if uri in self._subscriptions:
            self._subscriptions[uri].discard(client_id)
            if not self._subscriptions[uri]:
                del self._subscriptions[uri]
        
        if client_id in self._client_subscriptions:
            self._client_subscriptions[client_id].discard(uri)
            if not self._client_subscriptions[client_id]:
                del self._client_subscriptions[client_id]
        
        logger.info(f"Client {client_id} unsubscribed from {uri}")
        return True
    
    def get_subscriptions(self, client_id: str) -> Set[str]:
        """Get all URIs a client is subscribed to."""
        return self._client_subscriptions.get(client_id, set())
    
    def get_subscribers(self, uri: str) -> Set[str]:
        """Get all clients subscribed to a URI."""
        return self._subscriptions.get(uri, set())
    
    # =========================================================================
    # Resource Discovery
    # =========================================================================
    
    def get_resource_list(self) -> List[Resource]:
        """Get list of all available resources."""
        resources = [
            Resource(
                uri="mecris://walk/{date}",
                name="Walk Data",
                description="Walk data for a specific date (YYYY-MM-DD)",
                mimeType="application/json",
            ),
            Resource(
                uri="mecris://walk/today",
                name="Today's Walk",
                description="Walk data for today",
                mimeType="application/json",
            ),
            Resource(
                uri="mecris://language/{lang}",
                name="Language Stats",
                description="Language review stats for a specific language",
                mimeType="application/json",
            ),
            Resource(
                uri="mecris://language/all",
                name="All Languages",
                description="All language review statistics",
                mimeType="application/json",
            ),
            Resource(
                uri="mecris://budget",
                name="Budget Status",
                description="Current budget status and remaining balance",
                mimeType="application/json",
            ),
            Resource(
                uri="mecris://health/{date}",
                name="Health Data",
                description="Health/activity data for a specific date",
                mimeType="application/json",
            ),
            Resource(
                uri="mecris://aggregate",
                name="Aggregate Status",
                description="Daily aggregate status (walk, arabic, greek)",
                mimeType="application/json",
            ),
            Resource(
                uri="mecris://narrator/context",
                name="Narrator Context",
                description="Full narrator context with goals, budget, recommendations",
                mimeType="application/json",
            ),
            Resource(
                uri="mecris://health/today",
                name="Today's Health",
                description="Health/activity data for today",
                mimeType="application/json",
            ),
        ]
        return resources
    
    def get_resource_templates(self) -> List[ResourceTemplate]:
        """Get list of resource templates (URI templates with variables)."""
        templates = [
            ResourceTemplate(
                uriTemplate="mecris://walk/{date}",
                name="Walk Data by Date",
                description="Walk data for a specific date in YYYY-MM-DD format",
                mimeType="application/json",
            ),
            ResourceTemplate(
                uriTemplate="mecris://language/{lang}",
                name="Language Stats by Language",
                description="Language review stats for a specific language code",
                mimeType="application/json",
            ),
            ResourceTemplate(
                uriTemplate="mecris://health/{date}",
                name="Health Data by Date",
                description="Health/activity data for a specific date in YYYY-MM-DD format",
                mimeType="application/json",
            ),
        ]
        return templates
    
    async def list_resources(self) -> List[Resource]:
        """List all available resources."""
        return self.get_resource_list()
    
    async def list_resource_templates(self) -> List[ResourceTemplate]:
        """List all resource templates."""
        return self.get_resource_templates()
    
    # =========================================================================
    # Resource Reading
    # =========================================================================
    
    def _parse_uri(self, uri: str) -> Optional[Dict[str, Any]]:
        """Parse a Mecris URI into components."""
        if not uri.startswith("mecris://"):
            return None
        
        path = uri[9:]  # Remove "mecris://"
        parts = path.split("/")
        
        if not parts:
            return None
        
        resource_type = parts[0]
        params = {"type": resource_type}
        
        if resource_type == "walk" and len(parts) > 1:
            params["date"] = parts[1]
        elif resource_type == "language" and len(parts) > 1:
            params["lang"] = parts[1]
        elif resource_type == "health" and len(parts) > 1:
            params["date"] = parts[1]
        elif resource_type == "language" and len(parts) == 1:
            params["lang"] = "all"
        
        return params
    
    async def read_resource(self, uri: str) -> Dict[str, Any]:
        """Read a resource by URI."""
        params = self._parse_uri(uri)
        if not params:
            raise ValueError(f"Invalid Mecris URI: {uri}")
        
        resource_type = params.get("type")
        
        # Import here to avoid circular imports
        from mcp_server import (
            get_cached_daily_activity,
            get_language_velocity_stats,
            get_narrator_context,
            get_daily_aggregate_status,
            get_cached_beeminder_goals,
            usage_tracker,
            neon_checker,
            get_cached_beeminder_goals,
        )
        
        try:
            if resource_type == "walk":
                date_str = params.get("date", "today")
                if date_str == "today":
                    # Get today's walk data
                    walk_data = await get_cached_daily_activity("bike")
                    return {
                        "uri": f"mecris://walk/today",
                        "mimeType": "application/json",
                        "text": json.dumps(walk_data, default=str, indent=2)
                    }
                else:
                    # For specific date, would need to query DB
                    return {
                        "uri": uri,
                        "mimeType": "application/json",
                        "text": json.dumps({"error": "Historical walk queries not yet implemented"}, indent=2)
                    }
            
            elif resource_type == "language":
                lang = params.get("lang", "all")
                lang_stats = await get_language_velocity_stats()
                
                if lang == "all":
                    return {
                        "uri": "mecris://language/all",
                        "mimeType": "application/json",
                        "text": json.dumps(lang_stats, default=str, indent=2)
                    }
                elif lang in lang_stats:
                    return {
                        "uri": f"mecris://language/{lang}",
                        "mimeType": "application/json",
                        "text": json.dumps(lang_stats[lang], default=str, indent=2)
                    }
                else:
                    return {
                        "uri": uri,
                        "mimeType": "application/json",
                        "text": json.dumps({"error": f"Language {lang} not found"}, indent=2)
                    }
            
            elif resource_type == "budget":
                from mcp_server import usage_tracker
                budget = usage_tracker.get_budget_status()
                return {
                    "uri": "mecris://budget",
                    "mimeType": "application/json",
                    "text": json.dumps(budget, default=str, indent=2)
                }
            
            elif resource_type == "health":
                date_str = params.get("date", "today")
                if date_str == "today":
                    from mcp_server import neon_checker
                    walk = neon_checker.get_latest_walk()
                    return {
                        "uri": "mecris://health/today",
                        "mimeType": "application/json",
                        "text": json.dumps(walk, default=str, indent=2)
                    }
                else:
                    return {
                        "uri": uri,
                        "mimeType": "application/json",
                        "text": json.dumps({"error": "Historical health queries not yet implemented"}, indent=2)
                    }
            
            elif resource_type == "aggregate":
                from mcp_server import get_daily_aggregate_status
                agg = await get_daily_aggregate_status()
                return {
                    "uri": "mecris://aggregate",
                    "mimeType": "application/json",
                    "text": json.dumps(agg, default=str, indent=2)
                }
            
            elif resource_type == "narrator":
                ctx = await get_narrator_context()
                return {
                    "uri": "mecris://narrator/context",
                    "mimeType": "application/json",
                    "text": json.dumps(ctx, default=str, indent=2)
                }
            
            else:
                raise ValueError(f"Unknown resource type: {resource_type}")
    
    # =========================================================================
    # Subscription Management
    # =========================================================================
    
    def subscribe_client(self, uri: str, client_id: str) -> bool:
        """Subscribe a client to a resource URI."""
        if uri not in self._subscriptions:
            self._subscriptions[uri] = set()
        self._subscriptions[uri].add(client_id)
        
        if client_id not in self._client_subscriptions:
            self._client_subscriptions[client_id] = set()
        self._client_subscriptions[client_id].add(uri)
        
        logger.info(f"Client {client_id} subscribed to {uri}")
        return True
    
    def unsubscribe_client(self, uri: str, client_id: str) -> bool:
        """Unsubscribe a client from a resource URI."""
        if uri in self._subscriptions:
            self._subscriptions[uri].discard(client_id)
            if not self._subscriptions[uri]:
                del self._subscriptions[uri]
        
        if client_id in self._client_subscriptions:
            self._client_subscriptions[client_id].discard(uri)
            if not self._client_subscriptions[client_id]:
                del self._client_subscriptions[client_id]
        
        logger.info(f"Client {client_id} unsubscribed from {uri}")
        return True
    
    def get_client_subscriptions(self, client_id: str) -> Set[str]:
        """Get all URIs a client is subscribed to."""
        return self._client_subscriptions.get(client_id, set())
    
    def get_resource_subscribers(self, uri: str) -> Set[str]:
        """Get all clients subscribed to a URI."""
        return self._subscriptions.get(uri, set())
    
    async def notify_subscribers(self, uri: str):
        """Notify all subscribers of a resource change."""
        await self.notify_resource_changed(uri)


# Global resource manager instance (initialized in mcp_server.py)
_resource_manager: Optional['ResourceManager'] = None


def get_resource_manager() -> Optional['ResourceManager']:
    """Get the global resource manager instance."""
    return _resource_manager


def set_resource_manager(manager: 'ResourceManager'):
    """Set the global resource manager instance."""
    global _resource_manager
    _resource_manager = manager


def create_resource_manager(mcp: FastMCP) -> ResourceManager:
    """Create and return a new ResourceManager instance."""
    global _resource_manager
    _resource_manager = ResourceManager(mcp)
    return _resource_manager