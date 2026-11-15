import re

def refactor_file(file_path):
    with open(file_path, 'r') as f:
        content = f.read()

    # Find connection.query or connection.execute, capture until closing paren
    # But this is tricky because of nested parens.
    # It's better to just replace ])? with ]).await? and ]); with ]).await;
    # But only if it follows a connection.query or execute.
    
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if 'connection.query' in line or 'connection.execute' in line or '].await' in line:
            # Let's just do a simpler search and replace line by line for common patterns
            if '])?' in line and ']).await?' not in line:
                lines[i] = line.replace('])?', ']).await?')
            if ']);' in line and ']).await;' not in line:
                lines[i] = line.replace(']);', ']).await;')
            if '(query, &[])?' in line:
                lines[i] = line.replace('(query, &[])?', '(query, &[]).await?')
            if '(walk_query, &[])?' in line:
                lines[i] = line.replace('(walk_query, &[])?', '(walk_query, &[]).await?')

    with open(file_path, 'w') as f:
        f.write('\n'.join(lines))

if __name__ == "__main__":
    refactor_file("mecris-go-spin/sync-service/src/lib.rs")
