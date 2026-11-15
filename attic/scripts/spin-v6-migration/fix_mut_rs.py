import re

def refactor_file(file_path):
    with open(file_path, 'r') as f:
        content = f.read()

    # 1. rs = connection.query -> mut rs = connection.query
    content = content.replace('let walk_rs = connection.query', 'let mut walk_rs = connection.query')
    content = content.replace('let lang_rs = connection.query', 'let mut lang_rs = connection.query')
    content = content.replace('let user_rs = connection.query', 'let mut user_rs = connection.query')
    content = content.replace('let budget_rs = connection.query', 'let mut budget_rs = connection.query')
    content = content.replace('let walk_stats_rs = connection.query', 'let mut walk_stats_rs = connection.query')
    content = content.replace('let pulse_rs = connection.query', 'let mut pulse_rs = connection.query')
    content = content.replace('let rs = connection.query', 'let mut rs = connection.query')
    content = content.replace('let mcp_rows = connection.query', 'let mut mcp_rows = connection.query')
    content = content.replace('let row_set = connection.query', 'let mut row_set = connection.query')
    content = content.replace('let token_rs = connection.query', 'let mut token_rs = connection.query')
    content = content.replace('let mcp_active_rs = connection.query', 'let mut mcp_active_rs = connection.query')

    # Fix double mut
    content = content.replace('let mut mut ', 'let mut ')

    with open(file_path, 'w') as f:
        f.write(content)

if __name__ == "__main__":
    refactor_file("mecris-go-spin/sync-service/src/lib.rs")
