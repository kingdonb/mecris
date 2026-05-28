use spin_sdk::{
    http::{Request, Response, IntoResponse},
    http_service,
};

#[http_service]
async fn handle_hello(_req: Request) -> anyhow::Result<impl IntoResponse> {
    Ok(Response::builder()
        .status(200)
        .header("content-type", "text/plain")
        .body("Hello from SDK v6!".to_string())?)
}
