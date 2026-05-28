import re

def refactor_file(file_path):
    with open(file_path, 'r') as f:
        content = f.read()

    # The issue: .rows()? is now invalid because it's a stream, not a Result
    # And we can't consume the stream multiple times (e.g. walk_rs.rows()?.is_empty() then walk_rs.rows()?[0][0])
    
    # Let's fix this by finding every `let rs_name = connection.query(...).await?`
    # and appending `let rs_name_rows = rs_name.rows().collect().await;`
    # and then replacing `rs_name.rows()?` and `rs_name.rows` with `rs_name_rows`
    
    # First, let's revert `.rows()?` back to `.rows` to make it easier to match.
    content = content.replace('.rows()?', '.rows')

    lines = content.split('\n')
    new_lines = []
    
    for line in lines:
        new_lines.append(line)
        match = re.search(r'let\s+(mut\s+)?(\w+)\s*=\s*connection\.query.*\.await\?;', line)
        if match:
            rs_name = match.group(2)
            rows_name = f"{rs_name}_vec"
            indent = " " * (len(line) - len(line.lstrip()))
            new_lines.append(f"{indent}let {rows_name} = {rs_name}.rows().collect().await;")
            
    content = '\n'.join(new_lines)
    
    # Now replace occurrences
    rs_names = set(re.findall(r'let\s+(?:mut\s+)?(\w+)\s*=\s*connection\.query', content))
    for rs_name in rs_names:
        rows_name = f"{rs_name}_vec"
        
        # Replace `rs_name.rows` with `rows_name`
        content = content.replace(f"{rs_name}.rows", rows_name)

    # Some manual fixes for where I messed up the loop variables earlier
    content = content.replace('let rows_vec = lang_rs_vec; for row in rows_vec {', 'for row in lang_rs_vec {')
    content = content.replace('let rows_vec = user_rs_vec; for row in rows_vec {', 'for row in user_rs_vec {')
    content = content.replace('let rows_vec = row_set_vec; for row in rows_vec {', 'for row in row_set_vec {')
    content = content.replace('let rows_vec = pulse_rs_vec; for row in rows_vec {', 'for row in pulse_rs_vec {')
    content = content.replace('let rows_vec = rs_vec; for row in rows_vec {', 'for row in rs_vec {')

    with open(file_path, 'w') as f:
        f.write(content)

if __name__ == "__main__":
    refactor_file("mecris-go-spin/sync-service/src/lib.rs")
