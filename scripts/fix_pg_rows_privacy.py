import re

def refactor_file(file_path):
    with open(file_path, 'r') as f:
        content = f.read()

    # 1. Update result.rows to result.rows()
    # Be careful not to replace things that aren't PG results, but in this file
    # .rows is almost always on a row_set or similar.
    content = re.sub(r'(\w+)\.rows(?!\()', r'\1.rows()', content)

    with open(file_path, 'w') as f:
        f.write(content)

if __name__ == "__main__":
    refactor_file("mecris-go-spin/sync-service/src/lib.rs")
