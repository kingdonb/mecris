#!/usr/bin/env python3
"""
Token Killer: A utility to minimize token usage in LLM contexts.
Can be used to:
1. Strip comments and docstrings from code.
2. Shorten JSON schemas.
3. Minimize Markdown files.
"""

import sys
import json
import re

def kill_json_tokens(data):
    """Minimize JSON data by removing unnecessary keys for LLM understanding."""
    if isinstance(data, dict):
        # Example: Remove 'title' from JSON Schema if 'name' exists
        # or shorten 'description' to the first sentence.
        new_data = {}
        for k, v in data.items():
            if k == "description" and isinstance(v, str):
                new_data[k] = v.split(".")[0] + "."
            elif k == "input_schema": # MCP specific
                new_data[k] = kill_json_tokens(v)
            else:
                new_data[k] = kill_json_tokens(v)
        return new_data
    elif isinstance(data, list):
        return [kill_json_tokens(item) for item in data]
    return data

def kill_markdown_tokens(text):
    """Strip unnecessary fluff from Markdown."""
    # Remove HTML comments
    text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)
    # Remove multiple newlines
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: token_killer.py <file>")
        sys.exit(1)
    
    file_path = sys.argv[1]
    with open(file_path, 'r') as f:
        content = f.read()
    
    if file_path.endswith('.json'):
        data = json.loads(content)
        minimized = kill_json_tokens(data)
        print(json.dumps(minimized, indent=None))
    elif file_path.endswith('.md'):
        print(kill_markdown_tokens(content))
    else:
        # Generic line-based minimization
        lines = content.splitlines()
        for line in lines:
            line = line.strip()
            if line and not line.startswith('#') and not line.startswith('//'):
                print(line)
