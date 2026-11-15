import re

def refactor_file(file_path):
    with open(file_path, 'r') as f:
        content = f.read()

    # Add import
    content = content.replace('use futures::TryFutureExt;', 'use futures::TryFutureExt;\nuse http_body_util::BodyExt;')

    # Fix body bytes extraction
    # Old: let body_bytes = req.into_body();
    # New: let body_bytes = req.into_body().collect().await.map_err(|e| anyhow::anyhow!("Body error: {:?}", e))?.to_bytes();
    
    content = content.replace('let body_bytes = req.into_body();', 'let body_bytes = req.into_body().collect().await.map_err(|e| anyhow::anyhow!("Body error"))?.to_bytes();')
    content = content.replace('let body = req.into_body();', 'let body = req.into_body().collect().await.map_err(|e| anyhow::anyhow!("Body error"))?.to_bytes();')

    with open(file_path, 'w') as f:
        f.write(content)

if __name__ == "__main__":
    refactor_file("mecris-go-spin/sync-service/src/lib.rs")
