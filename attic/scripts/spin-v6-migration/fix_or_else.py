import re

def refactor_file(file_path):
    with open(file_path, 'r') as f:
        content = f.read()

    # Case 1: Multi-line or_else
    replacement1 = '''    let db_url = match variables::get("db_url").await {
        Ok(v) if !v.is_empty() => v,
        _ => variables::get("neon_db_url").await.map_err(|e| anyhow::anyhow!("db_url/neon_db_url fetch failed: {:?}", e))?
    };'''
    
    pattern1 = r'    let db_url = variables::get\("db_url"\)\.await\s*\.or_else\(\|_\| variables::get\("neon_db_url"\)\.await\)\s*\.map_err\(\|e\| anyhow::anyhow\!\("db_url/neon_db_url fetch failed: \{\:\?\}", e\)\)\?;'
    
    content = re.sub(pattern1, replacement1, content)

    # Case 2: inline match or_else
    replacement2 = '''            match match variables::get("db_url").await { Ok(v) if !v.is_empty() => Ok(v), _ => variables::get("neon_db_url").await } {'''
    pattern2 = r'            match variables::get\("db_url"\)\.await\.or_else\(\|_\| variables::get\("neon_db_url"\)\.await\) \{'
    content = re.sub(pattern2, replacement2, content)

    with open(file_path, 'w') as f:
        f.write(content)

if __name__ == "__main__":
    refactor_file("mecris-go-spin/sync-service/src/lib.rs")
