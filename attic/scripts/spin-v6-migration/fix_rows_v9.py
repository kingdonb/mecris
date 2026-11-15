import re

def refactor_file(file_path):
    with open(file_path, 'r') as f:
        content = f.read()

    # 1. Fix the bad `let xxx_vec = xxx_vec().collect().await;` calls
    content = re.sub(r'let (\w+)_vec = \1_vec\(\)\.collect\(\)\.await;', r'let \1_vec = \1.rows().collect::<Vec<_>>().await;', content)
    content = re.sub(r'let (\w+)_vec = \1\(\)\.collect\(\)\.await;', r'let \1_vec = \1.rows().collect::<Vec<_>>().await;', content)

    # 2. Fix dereferences
    content = content.replace('*i > 0', '*i > 0') # No change needed, but wait
    # In &row[0], if row is Vec<DbValue>, &row[0] is &DbValue.
    # match &row[0] { DbValue::Int64(i) => ... } matches &DbValue against &DbValue::Int64, 
    # so `i` is bound by reference: `i: &i64`.
    # Therefore `*i` is correct.

    with open(file_path, 'w') as f:
        f.write(content)

if __name__ == "__main__":
    refactor_file("mecris-go-spin/sync-service/src/lib.rs")
