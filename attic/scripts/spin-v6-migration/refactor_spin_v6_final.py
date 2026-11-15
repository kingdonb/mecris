import re

def refactor_file(file_path):
    with open(file_path, 'r') as f:
        content = f.read()

    # 1. Imports
    content = content.replace('http_component,\n', 'http_service,\n')
    content = content.replace('IntoResponse, Request, Response', 'Request, Response, Method, IntoResponse')
    content = content.replace('ParameterValue, DbValue', 'ParameterValue, DbValue, Decode')

    # 2. Helpers
    helpers = """
fn json_response<T: Serialize>(status: u16, data: &T) -> anyhow::Result<Response<String>> {
    Ok(Response::builder().status(status).header("content-type", "application/json").header("access-control-allow-origin", "*").body(serde_json::to_string(data)?)?)
}

fn text_response(status: u16, text: &str) -> anyhow::Result<Response<String>> {
    Ok(Response::builder().status(status).header("access-control-allow-origin", "*").body(text.to_string())?)
}
"""
    content = content.replace('use spin_cron_sdk::{cron_component, Metadata};\n', 'use spin_cron_sdk::{cron_component, Metadata};\nuse futures::TryFutureExt;\nuse http_body_util::BodyExt;\n' + helpers)

    # 3. add_cors
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
    builder.body(resp.into_body()).unwrap()
}''',
'''fn add_cors(mut resp: Response<String>) -> Response<String> {
    resp.headers_mut().insert("access-control-allow-origin", spin_sdk::http::HeaderValue::from_str("*").unwrap());
    resp
}'''
    )

    # 4. handle_cron db_url
    content = content.replace(
        'let db_url = match variables::get("db_url").or_else(|_| variables::get("neon_db_url")) {',
        'let db_url = match variables::get("db_url").await {\n        Ok(url) if !url.is_empty() => url,\n        _ => match variables::get("neon_db_url").await {\n            Ok(url) if !url.is_empty() => url,\n            _ => return Ok(()),\n        }\n    };'
    )

    # 5. Main Handler
    content = content.replace('#[http_component]', '#[http_service]')
    content = content.replace('async fn handle_sync_service(req: Request) -> anyhow::Result<Response> {', 'async fn handle_sync_service(req: Request) -> anyhow::Result<Response<String>> {')
    content = content.replace('let path = req.path();', 'let path = req.uri().path();')

    # Handler routing
    content = content.replace('Method::Options', 'Method::OPTIONS')
    content = content.replace('Method::Post', 'Method::POST')
    content = content.replace('Method::Get', 'Method::GET')

    content = content.replace('.build());\n    }', '.body(String::new())?);\n    }')
    content = re.sub(r'Response::builder\(\)\.status\((401|404|405)\)\.body\("([^"]+)"\)\.build\(\)', r'text_response(\1, "\2")?', content)

    # 6. Global Variables
    content = re.sub(r'variables::get\("([^"]+)"\)(?!\.await)', r'variables::get("\1").await', content)
    # Fix single line or_else
    content = re.sub(
        r'let db_url = variables::get\("db_url"\)\.await\.or_else\(\|_\| variables::get\("neon_db_url"\)\.await\)(\?)?;',
        r'let db_url = match variables::get("db_url").await { Ok(v) if !v.is_empty() => v, _ => variables::get("neon_db_url").await? };',
        content
    )
    content = content.replace('variables::get("db_url").await.or_else(|_| variables::get("neon_db_url").await)', 'match variables::get("db_url").await { Ok(v) if !v.is_empty() => Ok(v), _ => variables::get("neon_db_url").await }')

    # 7. Global PG
    content = re.sub(r'Connection::open\((.*?)\)\?', r'Connection::open(\1).await?', content)
    content = re.sub(r'connection\.execute\((.*?)\)(?!\.await|;)', r'connection.execute(\1).await', content)
    content = re.sub(r'connection\.query\((.*?)\)(?!\.await|;)', r'connection.query(\1).await', content)

    # 8. Async helpers
    content = content.replace('fn cloud_role() -> String {', 'async fn cloud_role() -> String {')
    content = content.replace('cloud_role()', 'cloud_role().await')
    content = content.replace('async fn cloud_role().await', 'async fn cloud_role()')

    content = content.replace('fn write_obs_status(', 'async fn write_obs_status(')
    content = content.replace('write_obs_status(&connection, &user_id, &cloud_role().await, "Stood down (conditions not met)", "Send Walk Reminder", None);', 'write_obs_status(&connection, &user_id, &cloud_role().await, "Stood down (conditions not met)", "Send Walk Reminder", None).await;')
    content = content.replace('write_obs_status(&connection, &user_id, &cloud_role().await, &stand_down_status, "Send Walk Reminder", None);', 'write_obs_status(&connection, &user_id, &cloud_role().await, &stand_down_status, "Send Walk Reminder", None).await;')
    content = content.replace('write_obs_status(&connection, &user_id, &cloud_role().await, "Sent Walk Reminder", "Send Walk Reminder", None);', 'write_obs_status(&connection, &user_id, &cloud_role().await, "Sent Walk Reminder", "Send Walk Reminder", None).await;')
    content = content.replace('write_obs_status(&connection, &user_id, &cloud_role().await, "Reminder failed", "Send Walk Reminder", Some(&e.to_string()));', 'write_obs_status(&connection, &user_id, &cloud_role().await, "Reminder failed", "Send Walk Reminder", Some(&e.to_string())).await;')

    # 9. Header parsing
    content = content.replace('req.header("authorization")', 'req.headers().get("authorization")')
    content = content.replace('req.header("x-internal-api-key").and_then(|v| v.as_str())', 'req.headers().get("x-internal-api-key").and_then(|v| v.to_str().ok())')
    content = content.replace('req.header("host").and_then(|v| v.as_str())', 'req.headers().get("host").and_then(|v| v.to_str().ok())')

    # 10. Body parsing
    content = content.replace('req.body()', 'req.into_body().collect().await.map_err(|_| anyhow::anyhow!("body err"))?.to_bytes()')
    # from_slice takes &[u8], bytes is convertible to &[u8]
    content = content.replace('from_slice(body_bytes)', 'from_slice(&body_bytes)')
    content = content.replace('from_slice(body)', 'from_slice(&body)')
    content = content.replace('from_slice(&&body)', 'from_slice(&body)')

    # 11. Rows collection (THE BIG ONE)
    # rs.rows returns Result<Vec<Row>> in WASI Preview 2/3 ?
    # Wait, the documentation said rows() is a method!
    # "result.rows()?"
    content = re.sub(r'(\w+)\.rows\[(\d+)\]\[(\d+)\]', r'\1.rows()?[\2][\3]', content)
    content = re.sub(r'(\w+)\.rows\.is_empty\(\)', r'\1.rows()?.is_empty()', content)
    content = re.sub(r'(\w+)\.rows\.first\(\)', r'\1.rows()?.first()', content)
    content = re.sub(r'for row in &(\w+)\.rows \{', r'let \1_vec = \1.rows()?; for row in \1_vec {', content)
    content = re.sub(r'for row in (\w+)\.rows \{', r'let \1_vec = \1.rows()?; for row in \1_vec {', content)

    # 12. Handler return types
    content = re.sub(r'async fn handle_([a-zA-Z0-9_]+)\(req: Request\) -> anyhow::Result<Response> \{', r'async fn handle_\1(req: Request) -> anyhow::Result<Response<String>> {', content)
    content = re.sub(r'async fn handle_([a-zA-Z0-9_]+)\(_req: Request\) -> anyhow::Result<Response> \{', r'async fn handle_\1(_req: Request) -> anyhow::Result<Response<String>> {', content)

    # 13. Other fixes
    content = content.replace('req.uri().contains("full=true")', 'req.uri().query().map(|q| q.contains("full=true")).unwrap_or(false)')

    # 14. Final response builds inside handlers
    content = re.sub(r'Ok\(Response::builder\(\)\.status\((200|201|202|500|400)\)\.header\("content-type", "application/json"\)\.body\(serde_json::to_string\((.*?)\)\.unwrap\(\)\)\.build\(\)\)', r'json_response(\1, \2)', content)

    with open(file_path, 'w') as f:
        f.write(content)

if __name__ == "__main__":
    refactor_file("mecris-go-spin/sync-service/src/lib.rs")
