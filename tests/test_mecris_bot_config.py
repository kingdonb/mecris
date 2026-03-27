import os
import re

def test_mecris_bot_turn_limit():
    workflow_path = ".github/workflows/mecris-bot.yml"
    assert os.path.exists(workflow_path)
    
    with open(workflow_path, "r") as f:
        content = f.read()
        # Find --max-turns 200
        assert "--max-turns 200" in content

def test_mecris_bot_prompt_constraints():
    prompt_path = "scripts/bot-prompt.txt"
    assert os.path.exists(prompt_path)
    
    with open(prompt_path, "r") as f:
        content = f.read()
        # Check turn limit (robot should believe it's 80)
        assert "STRICT LIMIT of 80 turns" in content
        # Check planning requirement
        assert "REPORT YOUR THOUGHTS in the issue" in content
        # Check TDG requirement
        assert "DO TDG" in content
        assert "Skill(tdg:atomic)" in content
