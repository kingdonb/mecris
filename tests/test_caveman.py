import pytest
from scripts.caveman import caveman_minimize_py

def test_caveman_collapse_class():
    code = """
class SmallTask:
    def __init__(self, name):
        self.name = name
    def run(self):
        print(f"Running {self.name}")
"""
    expected = """
def run_small_task(name):
    print(f"Running {name}")
"""
    # This is a bit ambitious for a simple script, but let's see.
    # Maybe caveman just strips everything but the core logic?
    
    minimized = caveman_minimize_py(code)
    assert "class SmallTask" not in minimized
    assert "def run" in minimized or "def run_small_task" in minimized
