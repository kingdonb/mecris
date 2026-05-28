import re

def refactor_file(file_path):
    with open(file_path, 'r') as f:
        lines = f.readlines()

    new_lines = []
    for line in lines:
        # Avoid lines that look like function definitions or are already async
        if "async fn" in line:
            new_lines.append(line)
            continue
        
        # 1. Update variables::get
        # Simple regex for variables::get("...") that aren't already awaited
        line = re.sub(r'variables::get\("([^"]+)"\)(?!\.await)', r'variables::get("\1").await', line)
        
        # 2. Update connection.execute and connection.query
        # These are usually on one line or have a specific ending
        line = re.sub(r'connection\.execute\((.*)\)(?!\.await|;)', r'connection.execute(\1).await', line)
        line = re.sub(r'connection\.query\((.*)\)(?!\.await|;)', r'connection.query(\1).await', line)
        
        # 3. .build() -> .build()?
        line = re.sub(r'\.build\(\)(?!\?)', r'.build()?', line)
        
        new_lines.append(line)

    # Secondary pass for multiline connection calls? 
    # Actually, let's just do the ones we can safely identify.
    
    with open(file_path, 'w') as f:
        f.writelines(new_lines)

if __name__ == "__main__":
    refactor_file("mecris-go-spin/sync-service/src/lib.rs")
