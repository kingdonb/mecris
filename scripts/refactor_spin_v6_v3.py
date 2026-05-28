import re

def refactor_file(file_path):
    with open(file_path, 'r') as f:
        content = f.read()

    # 1. Update imports
    content = content.replace(
        '    http::{Request, Response, Method, IntoResponse},\n    http_service,\n    pg::{Connection, ParameterValue, DbValue},\n    variables,',
        '    http::{Request, Response, Method, IntoResponse},\n    http_service,\n    pg::{Connection, ParameterValue, DbValue, Decode},\n    variables,'
    )

    # 2. Connection::open async
    content = re.sub(r'Connection::open\((.*?)\)\?', r'Connection::open(\1).await?', content)

    # 3. Variables async (including match)
    content = re.sub(r'variables::get\("([^"]+)"\)(?!\.await)', r'variables::get("\1").await', content)

    # 4. PG query/execute async
    content = re.sub(r'connection\.execute\((.*?)\)(?!\.await)', r'connection.execute(\1).await', content, flags=re.DOTALL)
    content = re.sub(r'connection\.query\((.*?)\)(?!\.await)', r'connection.query(\1).await', content, flags=re.DOTALL)

    # 5. Fix Result match pattern (it was becoming connection.query(...).await.match)
    # Actually my previous regex didn't catch that well.
    
    # 6. Collect rows (CRITICAL)
    # Convert .rows.is_empty() -> .rows().await?.is_empty()
    # Actually if query() returns QueryResult, rows() is async now too?
    # No, query() is async. result.rows() might be a stream.
    # Let's try .rows().collect::<Vec<_>>().await?
    content = re.sub(r'(\w+)\.rows\.is_empty\(\)', r'\1.rows().collect::<Vec<_>>().await?.is_empty()', content)
    content = re.sub(r'(\w+)\.rows\[(\d+)\]\[(\d+)\]', r'\1.rows().collect::<Vec<_>>().await?[\2][\3]', content)

    # 7. DbValue deref fix
    content = content.replace('=> *i', '=> i')
    content = content.replace('=> *f', '=> f')
    content = content.replace('=> *b', '=> b')
    content = content.replace('*i > 0', 'i > 0')

    with open(file_path, 'w') as f:
        f.write(content)

if __name__ == "__main__":
    refactor_file("mecris-go-spin/sync-service/src/lib.rs")
