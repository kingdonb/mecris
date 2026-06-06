import re

def caveman_minimize_py(code: str) -> str:
    """
    Caveman: Simplify complex structures.
    Currently: Flattens simple classes into functions.
    """
    # Look for a class with one method besides __init__
    class_match = re.search(r"class\s+(\w+):", code)
    if not class_match:
        return code

    class_name = class_match.group(1)
    
    # Extract methods
    methods = re.findall(r"def\s+(\w+)\(self,?\s*(.*?)\):", code)
    
    if len(methods) <= 2: # __init__ and one more, or just one
        run_method = None
        params = ""
        for name, p in methods:
            if name != "__init__":
                run_method = name
                params = p
                break
        
        if run_method:
            # Simple flattening: remove class def, remove self., rename function
            new_code = re.sub(r"class\s+\w+:.*?\n", "", code, flags=re.DOTALL)
            new_code = re.sub(r"def\s+__init__\(.*?\):.*?\n(\s+self\.\w+\s*=\s*\w+\n)*", "", new_code, flags=re.DOTALL)
            new_code = re.sub(r"def\s+" + run_method + r"\(self,?\s*(.*?)\):", r"def " + run_method + r"(\1):", new_code)
            new_code = re.sub(r"self\.", "", new_code)
            return new_code.strip()

    return code.strip()

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        with open(sys.argv[1], 'r') as f:
            print(caveman_minimize_py(f.read()))
