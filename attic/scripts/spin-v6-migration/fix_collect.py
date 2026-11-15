import re

def refactor_file(file_path):
    with open(file_path, 'r') as f:
        content = f.read()

    # .rows().collect::<Vec<_>>().await? -> .rows().collect().await
    content = content.replace('.rows().collect::<Vec<_>>().await?', '.rows().collect().await')

    with open(file_path, 'w') as f:
        f.write(content)

if __name__ == "__main__":
    refactor_file("mecris-go-spin/sync-service/src/lib.rs")
