import re

def refactor_file(file_path):
    with open(file_path, 'r') as f:
        content = f.read()

    # 1. Fix .build()) to ?)
    content = content.replace('.build())', '?)')
    # Also handle ones with no closing paren
    content = content.replace('.build()', '?')

    # 2. Fix connection.execute without await
    # Pattern: connection.execute(..., &[...])?
    content = re.sub(r'connection\.execute\((.*?)\)\?', r'connection.execute(\1).await?', content, flags=re.DOTALL)
    
    # Pattern: let _ = connection.execute(..., &[...]);
    content = re.sub(r'let _ = connection\.execute\((.*?)\);', r'let _ = connection.execute(\1).await;', content, flags=re.DOTALL)

    # Pattern: match connection.execute(...)
    content = re.sub(r'match connection\.execute\((.*?)\) \{', r'match connection.execute(\1).await {', content, flags=re.DOTALL)

    # 3. Double await fix
    content = content.replace('.await.await', '.await')

    with open(file_path, 'w') as f:
        f.write(content)

if __name__ == "__main__":
    refactor_file("mecris-go-spin/sync-service/src/lib.rs")
