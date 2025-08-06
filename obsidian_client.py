"""
Obsidian MCP Client - Interface to mcp-obsidian server
Handles structured access to Obsidian vault content
"""

import os
import re
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

import httpx
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("mecris.obsidian")

class ObsidianMCPClient:
    """Client for interfacing with mcp-obsidian server"""
    
    def __init__(self):
        self.host = os.getenv("OBSIDIAN_MCP_HOST", "localhost")
        self.port = int(os.getenv("OBSIDIAN_MCP_PORT", "3001"))
        self.base_url = f"http://{self.host}:{self.port}"
        self.vault_path = os.getenv("OBSIDIAN_VAULT_PATH", "")
        
        # HTTP client with timeout
        self.client = httpx.AsyncClient(timeout=10.0)
    
    async def health_check(self) -> str:
        """Check if mcp-obsidian server is accessible"""
        try:
            response = await self.client.get(f"{self.base_url}/health")
            return "ok" if response.status_code == 200 else "error"
        except Exception as e:
            logger.warning(f"Obsidian MCP server health check failed: {e}")
            return "unreachable"
    
    async def _mcp_call(self, tool: str, params: Dict[str, Any]) -> Any:
        """Make a call to mcp-obsidian server"""
        try:
            payload = {
                "tool": tool,
                "params": params
            }
            
            response = await self.client.post(
                f"{self.base_url}/mcp",
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code != 200:
                logger.error(f"MCP call failed: {response.status_code} - {response.text}")
                return None
            
            return response.json()
            
        except Exception as e:
            logger.error(f"MCP call to {tool} failed: {e}")
            return None
    
    async def search_vault(self, query: str) -> List[Dict[str, Any]]:
        """Search across all files in vault"""
        result = await self._mcp_call("search", {"query": query})
        return result.get("matches", []) if result else []
    
    async def get_file_content(self, file_path: str) -> str:
        """Get content of specific file"""
        result = await self._mcp_call("get_file_contents", {"file_path": file_path})
        return result.get("content", "") if result else ""
    
    async def list_vault_files(self) -> List[str]:
        """List all files in vault root"""
        result = await self._mcp_call("list_files_in_vault", {})
        return result.get("files", []) if result else []
    
    async def append_content(self, file_path: str, content: str) -> bool:
        """Append content to file"""
        result = await self._mcp_call("append_content", {
            "file_path": file_path,
            "content": content
        })
        return result.get("success", False) if result else False
    
    # Mecris-specific methods
    
    async def get_goals(self) -> List[Dict[str, Any]]:
        """Extract goals from vault by searching for goal patterns"""
        goals = []
        
        # Search for common goal patterns
        goal_patterns = [
            "## Goals",
            "# Goals", 
            "### Current Goals",
            "- [ ] Goal:",
            "**Goal:**"
        ]
        
        for pattern in goal_patterns:
            matches = await self.search_vault(pattern)
            for match in matches:
                file_path = match.get("file_path", "")
                content = await self.get_file_content(file_path)
                
                if content:
                    extracted_goals = self._parse_goals_from_content(content, file_path)
                    goals.extend(extracted_goals)
        
        # Deduplicate goals by content
        seen_goals = set()
        unique_goals = []
        
        for goal in goals:
            goal_key = f"{goal['content']}:{goal['source_file']}"
            if goal_key not in seen_goals:
                seen_goals.add(goal_key)
                unique_goals.append(goal)
        
        return unique_goals
    
    def _parse_goals_from_content(self, content: str, source_file: str) -> List[Dict[str, Any]]:
        """Parse goals from markdown content"""
        goals = []
        lines = content.split('\n')
        
        in_goals_section = False
        current_section = ""
        
        for i, line in enumerate(lines):
            line = line.strip()
            
            # Detect goals sections
            if re.match(r'^#{1,3}\s*Goals?\s*$', line, re.IGNORECASE):
                in_goals_section = True
                current_section = line
                continue
            
            # End of section
            if line.startswith('#') and in_goals_section:
                in_goals_section = False
                continue
            
            # Parse goal items in section
            if in_goals_section and line:
                goal_match = re.match(r'^[-*]\s*(\[[ x]\])?\s*(.+)', line)
                if goal_match:
                    checkbox = goal_match.group(1)
                    goal_text = goal_match.group(2).strip()
                    
                    goals.append({
                        "content": goal_text,
                        "completed": checkbox == "[x]" if checkbox else None,
                        "source_file": source_file,
                        "source_section": current_section,
                        "line_number": i + 1,
                        "last_updated": datetime.now().isoformat()
                    })
        
        return goals
    
    async def get_todos(self) -> List[Dict[str, Any]]:
        """Extract todos from vault by searching for checkbox patterns"""
        todos = []
        
        # Search for markdown checkboxes
        checkbox_matches = await self.search_vault("- [ ]")
        completed_matches = await self.search_vault("- [x]")
        
        all_matches = checkbox_matches + completed_matches
        
        for match in all_matches:
            file_path = match.get("file_path", "")
            content = await self.get_file_content(file_path)
            
            if content:
                extracted_todos = self._parse_todos_from_content(content, file_path)
                todos.extend(extracted_todos)
        
        # Deduplicate todos
        seen_todos = set()
        unique_todos = []
        
        for todo in todos:
            todo_key = f"{todo['content']}:{todo['source_file']}:{todo['line_number']}"
            if todo_key not in seen_todos:
                seen_todos.add(todo_key)
                unique_todos.append(todo)
        
        return unique_todos
    
    def _parse_todos_from_content(self, content: str, source_file: str) -> List[Dict[str, Any]]:
        """Parse todos from markdown content"""
        todos = []
        lines = content.split('\n')
        
        for i, line in enumerate(lines):
            # Match markdown checkboxes
            todo_match = re.match(r'^(\s*)[-*]\s*\[([ x])\]\s*(.+)', line)
            if todo_match:
                indent = todo_match.group(1)
                status = todo_match.group(2)
                todo_text = todo_match.group(3).strip()
                
                # Skip if it looks like a goal (contains "Goal:" pattern)
                if re.search(r'\bgoal\b', todo_text, re.IGNORECASE):
                    continue
                
                todos.append({
                    "content": todo_text,
                    "completed": status.lower() == "x",
                    "indent_level": len(indent),
                    "source_file": source_file,
                    "line_number": i + 1,
                    "priority": self._extract_priority(todo_text),
                    "tags": self._extract_tags(todo_text),
                    "last_updated": datetime.now().isoformat()
                })
        
        return todos
    
    def _extract_priority(self, text: str) -> Optional[str]:
        """Extract priority markers from todo text"""
        if "🔥" in text or "!!!" in text:
            return "high"
        elif "⚠️" in text or "!!" in text:
            return "medium"
        elif "!" in text:
            return "low"
        return None
    
    def _extract_tags(self, text: str) -> List[str]:
        """Extract #tags from todo text"""
        tag_pattern = r'#(\w+)'
        return re.findall(tag_pattern, text)
    
    async def get_daily_note(self, date: str) -> str:
        """Get daily note content for specific date"""
        # Common daily note patterns
        daily_note_patterns = [
            f"Daily Notes/{date}.md",
            f"{date}.md",
            f"Journal/{date}.md",
            f"daily/{date}.md"
        ]
        
        for pattern in daily_note_patterns:
            content = await self.get_file_content(pattern)
            if content:
                return content
        
        # If no exact match, search for the date
        matches = await self.search_vault(date)
        for match in matches:
            file_path = match.get("file_path", "")
            if date in file_path:
                return await self.get_file_content(file_path)
        
        return ""
    
    async def append_to_session_log(self, log_entry: str) -> bool:
        """Append session log entry to session log file"""
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = f"Mecris/session-log-{today}.md"
        
        # Create header if this is first entry of the day
        header = f"# Mecris Session Log - {today}\n\n"
        
        try:
            # Try to get existing content first
            existing_content = await self.get_file_content(log_file)
            if not existing_content:
                log_entry = header + log_entry
            
            return await self.append_content(log_file, log_entry)
            
        except Exception as e:
            logger.error(f"Failed to append session log: {e}")
            return False
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()