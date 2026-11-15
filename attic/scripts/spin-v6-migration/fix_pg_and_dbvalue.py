import re

def refactor_file(file_path):
    with open(file_path, 'r') as f:
        content = f.read()

    # 1. Connection::open(&db_url)? -> Connection::open(&db_url).await?
    content = re.sub(r'Connection::open\((.*?)\)\?', r'Connection::open(\1).await?', content)

    # 2. Fix DbValue dereferences
    # DbValue::Int64(i) => *i -> DbValue::Int64(i) => i
    content = content.replace('=> *i', '=> i')
    content = content.replace('=> *f', '=> f')
    content = content.replace('=> *b', '=> b')
    
    # Also handle things like *i > 0 or *i as u64
    content = content.replace('*i > 0', 'i > 0')
    content = content.replace('*i as u64', 'i as u64')

    with open(file_path, 'w') as f:
        f.write(content)

if __name__ == "__main__":
    refactor_file("mecris-go-spin/sync-service/src/lib.rs")
