import re

def refactor_file(file_path):
    with open(file_path, 'r') as f:
        content = f.read()

    # 1. Imports
    content = content.replace(
        'use spin_sdk::{\n    http::{IntoResponse, Request, Response},\n    http_component,\n    pg::{Connection, ParameterValue, DbValue},\n    variables,\n};',
        'use spin_sdk::{\n    http::{Request, Response, Method, IntoResponse},\n    http_service,\n    pg::{Connection, ParameterValue, DbValue, Decode},\n    variables,\n};'
    )

    # 2. handle_cron (surgical)
    content = content.replace(
        '    let db_url = match variables::get("db_url").or_else(|_| variables::get("neon_db_url")) {',
        '    let db_url = match variables::get("db_url").await {\n        Ok(url) if !url.is_empty() => url,\n        _ => match variables::get("neon_db_url").await {\n            Ok(url) if !url.is_empty() => url,\n            _ => return Ok(()),\n        }\n    };'
    )

    # 3. Main Handler
    content = content.replace('#[http_component]', '#[http_service]')
    content = content.replace('async fn handle_sync_service(req: Request) -> anyhow::Result<Response> {', 'async fn handle_sync_service(req: Request) -> anyhow::Result<Response<String>> {')
    content = content.replace('let path = req.path();', 'let path = req.uri().path();')

    # 4. Helper Functions
    content = content.replace('fn cloud_role() -> String {', 'async fn cloud_role() -> String {')
    content = content.replace('fn write_obs_status(', 'async fn write_obs_status(')
    # The problematic replacement:
    # if let Err(e) = connection.execute(obs_status_query(), &[ ... ]) {
    content = re.sub(
        r'if let Err\(e\) = connection\.execute\(obs_status_query\(\), &\[(.*?)\]\) \{',
        r'if let Err(e) = connection.execute(obs_status_query(), &[\1]).await {',
        content, flags=re.DOTALL
    )

    # 5. Global replacements (careful)
    content = re.sub(r'variables::get\("([^"]+)"\)(?!\.await)', r'variables::get("\1").await', content)
    content = re.sub(r'Connection::open\((.*?)\)\?', r'Connection::open(\1).await?', content)

    # connection.execute/query in other places
    # Only if it's NOT already followed by .await
    content = re.sub(r'connection\.execute\((.*?)\)(?!\.await|;)', r'connection.execute(\1).await', content)
    content = re.sub(r'connection\.query\((.*?)\)(?!\.await|;)', r'connection.query(\1).await', content)

    # 6. Response building (.build() removal)
    # Fix handle_sync_service preflight
    content = content.replace('.build());', '.body(String::new())?);')
    # Other .build() calls
    content = re.sub(r'\.body\((.*?)\)\.build\(\)', r'.body(\1)?', content)

    # 7. Rows access (collect rows)
    # result.rows[0][0] -> result.rows().collect::<Vec<_>>().await?[0][0]
    content = re.sub(r'(\w+)\.rows\[(\d+)\]\[(\d+)\]', r'\1.rows().collect::<Vec<_>>().await?[\2][\3]', content)
    content = re.sub(r'(\w+)\.rows\.is_empty\(\)', r'\1.rows().collect::<Vec<_>>().await?.is_empty()', content)
    content = re.sub(r'(\w+)\.rows\.first\(\)', r'\1.rows().collect::<Vec<_>>().await?.first()', content)

    # 8. Deref fix
    content = content.replace('=> *i', '=> i')
    content = content.replace('=> *f', '=> f')
    content = content.replace('=> *b', '=> b')
    content = content.replace('*i > 0', 'i > 0')

    with open(file_path, 'w') as f:
        f.write(content)

if __name__ == "__main__":
    refactor_file("mecris-go-spin/sync-service/src/lib.rs")
