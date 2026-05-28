import re

def refactor_file(file_path):
    with open(file_path, 'r') as f:
        content = f.read()

    # 1. Remove IncomingBody import
    content = content.replace('    wasip3::http::types::IncomingBody,\n', '')

    # 2. Undo IncomingBody::read_all
    # Instead of reading the stream, maybe req.body() works directly?
    content = re.sub(r'IncomingBody::read_all\(req\.into_body\(\), 1024 \* 1024\)\.await\?', 'req.body()', content)

    # 3. Fix obs_status_query().await
    content = content.replace('connection.execute(obs_status_query().await, &[', 'connection.execute(obs_status_query(), &[')

    with open(file_path, 'w') as f:
        f.write(content)

if __name__ == "__main__":
    refactor_file("mecris-go-spin/sync-service/src/lib.rs")
