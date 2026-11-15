import re

def refactor_file(file_path):
    with open(file_path, 'r') as f:
        content = f.read()

    # .rows()? -> .rows().collect().await
    content = content.replace('.rows()?', '.rows().collect().await')
    
    # let rows_vec = ...rows().collect().await; for row in rows_vec
    # The previous python script made: `let rows_vec = rs.rows()?; for row in rows_vec {`
    # That will naturally become `let rows_vec = rs.rows().collect().await; for row in rows_vec {`

    with open(file_path, 'w') as f:
        f.write(content)

if __name__ == "__main__":
    refactor_file("mecris-go-spin/sync-service/src/lib.rs")
