import pytest
import json
import os
from scripts.token_killer import kill_json_tokens, kill_markdown_tokens

def test_kill_json_tokens():
    data = {
        "name": "get_narrator_context",
        "description": "Get unified strategic context with goals, budget, and recommendations.",
        "input_schema": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "string",
                    "description": "The user ID to fetch context for."
                }
            }
        }
    }
    minimized = kill_json_tokens(data)
    
    # Check that description is shortened
    assert minimized["description"] == "Get unified strategic context with goals, budget, and recommendations."
    # Wait, the script says split(".")[0] + "."
    # "Get unified strategic context with goals, budget, and recommendations." has no internal "." except at the end.
    
    data2 = {"description": "First sentence. Second sentence."}
    minimized2 = kill_json_tokens(data2)
    assert minimized2["description"] == "First sentence."

def test_kill_markdown_tokens():
    text = "# Title\n\n<!-- comment -->\n\nContent\n\n\n\nMore content"
    minimized = kill_markdown_tokens(text)
    assert "<!-- comment -->" not in minimized
    assert "\n\n\n" not in minimized
    assert "Title" in minimized
    assert "More content" in minimized
