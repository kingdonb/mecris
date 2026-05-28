import re

def refactor_file(file_path):
    with open(file_path, 'r') as f:
        content = f.read()

    # 1. Imports
    content = content.replace(
        'use spin_sdk::{\n    http::{IntoResponse, Request, Response},\n    http_component,\n    pg::{Connection, ParameterValue, DbValue},\n    variables,\n};',
        'use spin_sdk::{\n    http::{Request, Response, Method, IntoResponse},\n    http_service,\n    pg::{Connection, ParameterValue, DbValue, Decode},\n    variables,\n    wasip3::http::types::IncomingBody,\n};'
    )
    # Add my custom response helpers right after imports
    helpers = """
fn json_response<T: Serialize>(status: u16, data: &T) -> anyhow::Result<Response<String>> {
    Ok(Response::builder()
        .status(status)
        .header("content-type", "application/json")
        .header("access-control-allow-origin", "*")
        .body(serde_json::to_string(data)?)?)
}

fn text_response(status: u16, text: &str) -> anyhow::Result<Response<String>> {
    Ok(Response::builder()
        .status(status)
        .header("access-control-allow-origin", "*")
        .body(text.to_string())?)
}
"""
    content = content.replace('use spin_cron_sdk::{cron_component, Metadata};', 'use spin_cron_sdk::{cron_component, Metadata};\nuse futures::TryFutureExt;\n' + helpers)

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
    content = re.sub(
        r'if let Err\(e\) = connection\.execute\(obs_status_query\(\), &\[(.*?)\]\) \{',
        r'if let Err(e) = connection.execute(obs_status_query(), &[\1]).await {',
        content, flags=re.DOTALL
    )

    # 5. Global replacements (careful)
    content = re.sub(r'variables::get\("([^"]+)"\)(?!\.await)', r'variables::get("\1").await', content)
    content = re.sub(r'Connection::open\((.*?)\)\?', r'Connection::open(\1).await?', content)

    content = re.sub(r'connection\.execute\((.*?)\)(?!\.await|;)', r'connection.execute(\1).await', content)
    content = re.sub(r'connection\.query\((.*?)\)(?!\.await|;)', r'connection.query(\1).await', content)

    # 6. Response building
    content = re.sub(r'Response::builder\(\)\.status\((401|404|405)\)\.body\("([^"]+)"\)\.build\(\)', r'text_response(\1, "\2")?', content)
    content = re.sub(r'Response::builder\(\)\.status\((401|404|405)\)\.body\("([^"]+)"\)\?', r'text_response(\1, "\2")?', content)
    content = re.sub(r'Response::builder\(\)\.status\((200|201|202|500)\)\.header\("content-type", "application/json"\)\.body\(serde_json::to_string\((.*?)\)\.unwrap\(\)\)\.build\(\)', r'json_response(\1, \2)?', content)

    # Preflight
    content = content.replace(
        '.header("access-control-allow-headers", "authorization, content-type, x-internal-api-key")\n            .build());',
        '.header("access-control-allow-headers", "authorization, content-type, x-internal-api-key")\n            .body(String::new())?);'
    )

    # 7. Rows access (spin_sdk::pg::QueryResult in v6 uses rows() which returns Result<Vec<Row>>)
    content = re.sub(r'(\w+)\.rows\[(\d+)\]\[(\d+)\]', r'\1.rows()?[\2][\3]', content)
    content = re.sub(r'(\w+)\.rows\.is_empty\(\)', r'\1.rows()?.is_empty()', content)
    content = re.sub(r'(\w+)\.rows\.first\(\)', r'\1.rows()?.first()', content)
    content = re.sub(r'for row in &(\w+)\.rows \{', r'let rows_vec = \1.rows()?; for row in rows_vec {', content)

    # 8. Additional v6 Fixes
    content = content.replace('req.header("authorization")', 'req.headers().get("authorization")')
    content = content.replace('req.header("x-internal-api-key")', 'req.headers().get("x-internal-api-key").and_then(|v| v.to_str().ok())')
    content = content.replace('req.header("x-internal-api-key").and_then(|v| v.as_str())', 'req.headers().get("x-internal-api-key").and_then(|v| v.to_str().ok())')
    
    # 9. Async calls
    content = content.replace('cloud_role()', 'cloud_role().await')
    content = content.replace('async fn cloud_role().await', 'async fn cloud_role()')
    
    # Fix write_obs_status calls
    content = content.replace('write_obs_status(&connection, &user_id, &cloud_role().await, "Stood down (conditions not met)", "Send Walk Reminder", None);', 'write_obs_status(&connection, &user_id, &cloud_role().await, "Stood down (conditions not met)", "Send Walk Reminder", None).await;')
    content = content.replace('write_obs_status(&connection, &user_id, &cloud_role().await, &stand_down_status, "Send Walk Reminder", None);', 'write_obs_status(&connection, &user_id, &cloud_role().await, &stand_down_status, "Send Walk Reminder", None).await;')
    content = content.replace('write_obs_status(&connection, &user_id, &cloud_role().await, "Sent Walk Reminder", "Send Walk Reminder", None);', 'write_obs_status(&connection, &user_id, &cloud_role().await, "Sent Walk Reminder", "Send Walk Reminder", None).await;')
    content = content.replace('write_obs_status(&connection, &user_id, &cloud_role().await, "Reminder failed", "Send Walk Reminder", Some(&e.to_string()));', 'write_obs_status(&connection, &user_id, &cloud_role().await, "Reminder failed", "Send Walk Reminder", Some(&e.to_string())).await;')
    
    # Method enum
    content = content.replace('Method::Options', 'Method::OPTIONS')
    content = content.replace('Method::Post', 'Method::POST')
    content = content.replace('Method::Get', 'Method::GET')

    # Return type for all handlers
    content = re.sub(r'async fn handle_([a-zA-Z0-9_]+)\(req: Request\) -> anyhow::Result<Response> \{', r'async fn handle_\1(req: Request) -> anyhow::Result<Response<String>> {', content)

    # 10. URI
    content = content.replace('req.uri().contains("full=true")', 'req.uri().query().map(|q| q.contains("full=true")).unwrap_or(false)')

    # 11. Body extraction
    content = content.replace('req.body()', 'IncomingBody::read_all(req.into_body(), 1024 * 1024).await?')
    content = content.replace('req.into_body()', 'IncomingBody::read_all(req.into_body(), 1024 * 1024).await?')
    # Fix the double replacement issue
    content = content.replace('IncomingBody::read_all(IncomingBody::read_all(req.into_body(), 1024 * 1024).await?, 1024 * 1024).await?', 'IncomingBody::read_all(req.into_body(), 1024 * 1024).await?')

    # 12. Fix the add_cors method
    content = content.replace(
'''fn add_cors(resp: Response) -> Response {
    let mut builder = Response::builder();
    builder.status(*resp.status());
    
    for (name, value) in resp.headers() {
        if let Ok(v_str) = std::str::from_utf8(value.as_ref()) {
            builder.header(name, v_str);
        }
    }
    
    builder.header("access-control-allow-origin", "*");
    builder.body(resp.into_body())?
}''',
'''fn add_cors(mut resp: Response<String>) -> Response<String> {
    resp.headers_mut().insert("access-control-allow-origin", "*".parse().unwrap());
    resp
}'''
    )

    with open(file_path, 'w') as f:
        f.write(content)

if __name__ == "__main__":
    refactor_file("mecris-go-spin/sync-service/src/lib.rs")
