import re

def refactor_file(file_path):
    with open(file_path, 'r') as f:
        content = f.read()

    # 1. URI contains
    content = content.replace('req.uri().contains("full=true")', 'req.uri().query().map(|q| q.contains("full=true")).unwrap_or(false)')

    # 2. clone().await
    content = content.replace('clone().await', 'clone()')
    content = content.replace('user_id.await', 'user_id')

    with open(file_path, 'w') as f:
        f.write(content)

if __name__ == "__main__":
    refactor_file("mecris-go-spin/sync-service/src/lib.rs")
