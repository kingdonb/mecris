import re

def refactor_file(file_path):
    with open(file_path, 'r') as f:
        content = f.read()

    # 1. 404 response
    content = content.replace('Response::builder().status(404).body("Not Found")?', 'text_response(404, "Not Found")?')

    # 2. Extract authorization header (req.header -> req.headers().get)
    content = content.replace('req.header("authorization")', 'req.headers().get("authorization")')

    # 3. body("Unauthorized")? -> text_response(401, "Unauthorized")?
    content = content.replace('return Ok(Response::builder().status(401).body("Unauthorized")?)', 'return text_response(401, "Unauthorized")')

    # 4. body("Unauthorized".to_string())? -> text_response(401, "Unauthorized")?
    content = content.replace('return Ok(Response::builder().status(401).body("Unauthorized".to_string())?)', 'return text_response(401, "Unauthorized")')

    with open(file_path, 'w') as f:
        f.write(content)

if __name__ == "__main__":
    refactor_file("mecris-go-spin/sync-service/src/lib.rs")
