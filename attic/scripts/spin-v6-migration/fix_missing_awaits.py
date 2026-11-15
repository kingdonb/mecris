import re

def refactor_file(file_path):
    with open(file_path, 'r') as f:
        content = f.read()

    # 1. Missing `.await` in connection.query(...)
    content = re.sub(r'connection\.query\(([^;]+?)\)\?;', r'connection.query(\1).await?;', content)

    # 2. Fix the user_id.clone().await error
    content = content.replace('user_id.clone().await', 'user_id.clone()')
    content = content.replace('ParameterValue::Str(user_id).await', 'ParameterValue::Str(user_id.clone())')

    with open(file_path, 'w') as f:
        f.write(content)

if __name__ == "__main__":
    refactor_file("mecris-go-spin/sync-service/src/lib.rs")
