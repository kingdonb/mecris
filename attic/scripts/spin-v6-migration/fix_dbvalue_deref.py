import re

def refactor_file(file_path):
    with open(file_path, 'r') as f:
        content = f.read()

    # Revert my bad DbValue fixes
    # DbValue::Int64(i) => i -> DbValue::Int64(i) => *i
    # Because 'i' is actually bound by reference when matching &row[x]
    content = re.sub(r'(DbValue::[a-zA-Z0-9]+\([a-zA-Z]\)) => ([a-zA-Z])', r'\1 => *\2', content)
    content = content.replace('i > 0', '*i > 0')
    content = content.replace('i as u64', '*i as u64')

    with open(file_path, 'w') as f:
        f.write(content)

if __name__ == "__main__":
    refactor_file("mecris-go-spin/sync-service/src/lib.rs")
