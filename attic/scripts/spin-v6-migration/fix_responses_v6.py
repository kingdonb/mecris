import re

def refactor_file(file_path):
    with open(file_path, 'r') as f:
        content = f.read()

    # 1. Remove .build() after .body(...)
    # Pattern: .body(anything).build()? or .body(anything).build()
    content = re.sub(r'\.body\((.*?)\)\.build\(\)\??', r'.body(\1)?', content, flags=re.DOTALL)

    # 2. Fix body(())? to body(String::new())? for Response<String>
    content = content.replace('.body(())?', '.body(String::new())?')

    # 3. Fix .body("...")? to .body("...".to_string())?
    # Simple strings only
    content = re.sub(r'\.body\("([^"]+)"\)\?', r'.body("\1".to_string())?', content)

    with open(file_path, 'w') as f:
        f.write(content)

if __name__ == "__main__":
    refactor_file("mecris-go-spin/sync-service/src/lib.rs")
