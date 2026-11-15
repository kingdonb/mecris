import re

def refactor_file(file_path):
    with open(file_path, 'r') as f:
        content = f.read()

    # 1. variables::get("...") -> variables::get("...").await
    # Only if not already followed by .await
    content = re.sub(r'variables::get\("([^"]+)"\)(?!\.await)', r'variables::get("\1").await', content)

    # 2. connection.execute(...) -> connection.execute(...).await
    # Only if not already followed by .await
    content = re.sub(r'connection\.execute\((.*?)\)(?!\.await)', r'connection.execute(\1).await', content, flags=re.DOTALL)

    # 3. connection.query(...) -> connection.query(...).await
    # Only if not already followed by .await
    content = re.sub(r'connection\.query\((.*?)\)(?!\.await)', r'connection.query(\1).await', content, flags=re.DOTALL)

    # 4. .build() -> .build()?
    # Only if not already followed by ?
    content = re.sub(r'\.build\(\)(?!\?)', r'.build()?', content)

    with open(file_path, 'w') as f:
        f.write(content)

if __name__ == "__main__":
    refactor_file("mecris-go-spin/sync-service/src/lib.rs")
