import re

def refactor_file(file_path):
    with open(file_path, 'r') as f:
        content = f.read()

    # 1. from_slice(body.to_vec()) -> from_slice(&body)
    content = content.replace('from_slice(body.to_vec())', 'from_slice(&body)')
    
    # Wait, my script earlier did:
    # let body = req.into_body().collect().await.map_err(|e| anyhow::anyhow!("Body error"))?.to_bytes();
    # So `body` is `bytes::Bytes`. `serde_json::from_slice(&body)` works.

    # Let's fix the other from_slice places
    content = content.replace('serde_json::from_slice(body_bytes)', 'serde_json::from_slice(&body_bytes)')
    content = content.replace('serde_json::from_slice(body)', 'serde_json::from_slice(&body)')
    # Fix accidental double references
    content = content.replace('from_slice(&&body)', 'from_slice(&body)')

    # 2. Fix the Response::builder().status().body().build() ones that I missed
    # I'll just change `.build())` to `?)` for those specific patterns.
    # Pattern: .body(anything).build())
    content = re.sub(r'\.body\((.*?)\)\.build\(\)\)', r'.body(\1)?)', content, flags=re.DOTALL)
    # Pattern: .body(anything).build()
    content = re.sub(r'\.body\((.*?)\)\.build\(\)', r'.body(\1)?', content, flags=re.DOTALL)

    # 3. Method Not Allowed was already fixed mostly, let's verify
    # Response::builder().status(405).body("Method Not Allowed".to_string())?
    
    with open(file_path, 'w') as f:
        f.write(content)

if __name__ == "__main__":
    refactor_file("mecris-go-spin/sync-service/src/lib.rs")
