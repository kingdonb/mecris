import pytest
from py_harness.mecris_harness import prune_history

def test_prune_history():
    messages = [
        {"role": "system", "content": "System prompt"},
        {"role": "user", "content": "User 1"},
        {"role": "assistant", "content": "Assistant 1"},
        {"role": "user", "content": "User 2"},
        {"role": "assistant", "content": "Assistant 2"},
        {"role": "user", "content": "User 3"},
        {"role": "assistant", "content": "Assistant 3"},
    ]
    # Prune to keep system + last 2 turns (4 messages)
    pruned = prune_history(messages, max_messages=5)
    
    assert len(pruned) == 5
    assert pruned[0]["role"] == "system"
    assert pruned[1]["role"] == "user"
    assert pruned[1]["content"] == "User 2"
    assert pruned[-1]["content"] == "Assistant 3"
