import re

with open('mecris-go-spin/sync-service/src/lib.rs', 'r') as f:
    content = f.read()

# 1. Add missing import
content = content.replace('use chrono::Timelike;', 'use chrono::{Timelike, TimeZone};')

# 2. Fix aggregate_step_count signature and implementation
# It should accept &Vec<spin_sdk::pg::Row>
content = content.replace(
    'fn aggregate_step_count(rs: &Vec<Vec<DbValue>>) -> i32 { rs.iter().filter_map(|r| match &r[0] { DbValue::Str(s) => s.parse::<i32>().ok(), _ => None }).max().unwrap_or(0) }',
    'fn aggregate_step_count(rs: &Vec<spin_sdk::pg::Row>) -> i32 { rs.iter().filter_map(|r| match &r[0] { DbValue::Str(s) => s.parse::<i32>().ok(), _ => None }).max().unwrap_or(0) }'
)

# 3. Fix the chrono syntax error
# chrono::Utc.from_utc_datetime(...) -> chrono::Utc.from_utc_datetime(...) is actually chrono::Utc.from_utc_datetime(&ndt)
# The user's error showed: chrono::Utc.from_utc_datetime(&ndt, chrono::Utc) which is wrong.
# It should be chrono::Utc.from_utc_datetime(&ndt)
content = content.replace(
    'chrono::Utc.from_utc_datetime(&ndt, chrono::Utc)',
    'chrono::Utc.from_utc_datetime(&ndt)'
)

# 4. Handle unused variables to clean up build output
content = content.replace('let tok = decrypt_token(&variables::get("twilio_auth_token_encrypted")', 'let _tok = decrypt_token(&variables::get("twilio_auth_token_encrypted")')

with open('mecris-go-spin/sync-service/src/lib.rs', 'w') as f:
    f.write(content)
