import re

def refactor_file(file_path):
    with open(file_path, 'r') as f:
        content = f.read()

    # Find all rs = connection.query(...).await?
    # Or just rs = connection.query(...)
    
    # Let's revert my previous bad collections first:
    content = content.replace('.rows().collect().await', '.rows')
    # now we have walk_rs.rows[0][0] etc. again (or walk_rs.rows.is_empty())
    
    # We want to declare `let rows = walk_rs.rows().collect().await;`
    # and then use `rows` instead of `walk_rs.rows`
    
    # To do this safely across the whole file:
    lines = content.split('\n')
    new_lines = []
    
    for line in lines:
        new_lines.append(line)
        # If the line defines a query result
        match = re.search(r'let\s+(mut\s+)?(\w+_rs|rs)\s*=\s*connection\.query.*\.await\?;', line)
        if match:
            rs_name = match.group(2)
            prefix = rs_name.split('_')[0] if '_' in rs_name else 'result'
            rows_name = f"{prefix}_rows"
            
            # We don't want to insert if it's already there
            # But let's assume it's not.
            indent = " " * (len(line) - len(line.lstrip()))
            new_lines.append(f"{indent}let {rows_name} = {rs_name}.rows().collect().await;")
            
    content = '\n'.join(new_lines)
    
    # Now replace the usages
    # e.g. walk_rs.rows.is_empty() -> walk_rows.is_empty()
    # e.g. walk_rs.rows[0][0] -> walk_rows[0][0]
    
    # Find all declared rs_names and their corresponding rows_names
    rs_names = set(re.findall(r'let\s+(?:mut\s+)?(\w+_rs|rs)\s*=\s*connection\.query', content))
    for rs_name in rs_names:
        prefix = rs_name.split('_')[0] if '_' in rs_name else 'result'
        rows_name = f"{prefix}_rows"
        
        # Replace occurrences
        content = content.replace(f"{rs_name}.rows", rows_name)
        
    with open(file_path, 'w') as f:
        f.write(content)

if __name__ == "__main__":
    refactor_file("mecris-go-spin/sync-service/src/lib.rs")
