import re

def refactor_file(file_path):
    with open(file_path, 'r') as f:
        content = f.read()

    # 1. Standardize query result collection
    # Pattern: let mut rs = connection.query(...).await?;
    # Fix: let rs = connection.query(...).await?; let rs_rows = rs.collect().await?;
    # Then change rs.rows usages to rs_rows
    
    lines = content.split('\n')
    new_lines = []
    rs_names = set()
    
    for line in lines:
        match = re.search(r'let\s+(mut\s+)?(\w+)\s*=\s*connection\.query.*\.await\?;', line)
        if match:
            rs_name = match.group(2)
            rs_names.add(rs_name)
            new_lines.append(line)
            indent = " " * (len(line) - len(line.lstrip()))
            new_lines.append(f"{indent}let {rs_name}_rows = {rs_name}.collect().await?;")
            continue
        
        # Avoid the messed up vec lines from previous runs
        if "_vec =" in line and ".rows().collect()" in line:
            continue
        if "_rows =" in line and ".rows().collect()" in line:
            continue
            
        new_lines.append(line)
            
    content = '\n'.join(new_lines)
    
    # 2. Map rs.rows, rs_vec, rs_rows to the new standardized rs_name_rows
    for rs_name in rs_names:
        content = content.replace(f"{rs_name}.rows", f"{rs_name}_rows")
        content = content.replace(f"{rs_name}_vec", f"{rs_name}_rows")
        content = content.replace(f"&{rs_name}_rows", f"&{rs_name}_rows") # no-op but safe

    # 3. Fix the Row index access
    # In v6, rs.collect() returns Vec<Row>. Row can be indexed: row[0]
    # But row[0] returns &DbValue. match &row[0] is correct.
    
    # 4. Fix redundant .build() or other response issues
    content = content.replace('.build())', '?)')
    content = content.replace('.build()', '?')
    
    # 5. Final check on the or_else pattern
    content = re.sub(
        r'variables::get\("db_url"\)\.await\.or_else\(\|_\| variables::get\("neon_db_url"\)\.await\)',
        r'match variables::get("db_url").await { Ok(v) if !v.is_empty() => Ok(v), _ => variables::get("neon_db_url").await }',
        content
    )

    with open(file_path, 'w') as f:
        f.write(content)

if __name__ == "__main__":
    refactor_file("mecris-go-spin/sync-service/src/lib.rs")
