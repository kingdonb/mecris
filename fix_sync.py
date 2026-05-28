import re

with open('mecris-go-spin/sync-service/src/lib.rs', 'r') as f:
    content = f.read()

# 1. Fix the last_sync date comparison logic in run_clozemaster_scraper
# We need to parse the UTC timestamp from the DB and compare the date part in NY time.

new_sync_logic = r'''
            let rows = conn.query("SELECT current_reviews, (beeminder_last_sync AT TIME ZONE 'UTC')::TEXT FROM language_stats WHERE user_id = $1 AND language_name = $2", &[ParameterValue::Str(uid.to_string()), ParameterValue::Str(lang.to_uppercase())]).await?.collect().await?;
            let (mut prev, mut lsync) = (-1, String::new());
            if !rows.is_empty() { 
                prev = match &rows[0][0] { DbValue::Int32(i) => *i, _ => -1 }; 
                lsync = match &rows[0][1] { DbValue::Str(s) => s.clone(), _ => String::new() }; 
            }
            let mut compl = tod; if lang == "ARABIC" { compl = (tod as f64 / 16.0) as i32; }
            conn.execute("INSERT INTO language_stats (user_id, language_name, current_reviews, tomorrow_reviews, next_7_days_reviews, beeminder_slug, daily_completions, last_points, total_points, last_updated) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, CURRENT_TIMESTAMP) ON CONFLICT (user_id, language_name) DO UPDATE SET current_reviews = EXCLUDED.current_reviews, tomorrow_reviews = EXCLUDED.tomorrow_reviews, next_7_days_reviews = EXCLUDED.next_7_days_reviews, beeminder_slug = EXCLUDED.beeminder_slug, daily_completions = EXCLUDED.daily_completions, last_points = EXCLUDED.last_points, total_points = EXCLUDED.total_points, last_updated = CURRENT_TIMESTAMP", &[ParameterValue::Str(uid.to_string()), ParameterValue::Str(lang.to_uppercase()), ParameterValue::Int32(cur), ParameterValue::Int32(tom), ParameterValue::Int32(n7), ParameterValue::Str(beem.to_string()), ParameterValue::Int32(compl), ParameterValue::Int32(tot), ParameterValue::Int32(tot)]).await?;
            
            if !beem.is_empty() {
                let now_ny = chrono::Utc::now().with_timezone(&chrono_tz::America::New_York);
                let today_ny = now_ny.format("%Y-%m-%d").to_string();
                
                // lsync from DB is "YYYY-MM-DD HH:MM:SS..." (UTC)
                let already_synced_today = if lsync.is_empty() { false } else {
                    // Simple string prefix check works if we normalize the DB string to the same date format
                    lsync.starts_with(&today_ny) 
                    || match chrono::NaiveDateTime::parse_from_str(lsync.split('.').next().unwrap_or(""), "%Y-%m-%d %H:%M:%S") {
                        Ok(ndt) => {
                            let dt_utc = chrono::Utc.from_utc_datetime(&ndt, chrono::Utc);
                            dt_utc.with_timezone(&chrono_tz::America::New_York).format("%Y-%m-%d").to_string() == today_ny
                        },
                        Err(_) => false
                    }
                };

                if cur != prev || !already_synced_today {
                    let comment = format!("Auto-synced from Clozemaster (Cloud) at {} | Tomorrow: {} | 7-day: {}", now_ny.format("%Y-%m-%d %H:%M"), tom, n7);
                    // Use a unique requestid based on user, goal, date, and current review count to prevent duplicates
                    let requestid = format!("{}-{}-{}-{}", uid, beem, today_ny, cur);
                    if let Ok(_) = push_to_beeminder_idempotent(uid, beem, cur as f64, &comment, &requestid, &conn).await { 
                        conn.execute("UPDATE language_stats SET beeminder_last_sync = CURRENT_TIMESTAMP WHERE user_id = $1 AND language_name = $2", &[ParameterValue::Str(uid.to_string()), ParameterValue::Str(lang.to_uppercase())]).await?; 
                    }
                }
'''

content = re.sub(
    r'let rs = conn\.query\("SELECT current_reviews, beeminder_last_sync::TEXT FROM language_stats WHERE user_id = \$1 AND language_name = \$2",.*?if !beem\.is_empty\(\) \{.*?\}\s*\}',
    new_sync_logic + '            }',
    content, flags=re.DOTALL
)

# 2. Add push_to_beeminder_idempotent helper
content = content.replace(
    'async fn push_to_beeminder(uid: &str, slug: &str, val: f64, comment: &str, conn: &Connection) -> anyhow::Result<()> {',
    '''async fn push_to_beeminder_idempotent(uid: &str, slug: &str, val: f64, comment: &str, requestid: &str, conn: &Connection) -> anyhow::Result<()> {
    let rs = conn.query("SELECT beeminder_token_encrypted, beeminder_user_encrypted FROM users WHERE pocket_id_sub = $1", &[ParameterValue::Str(uid.to_string())]).await?.collect().await?;
    if rs.is_empty() { return Err(anyhow::anyhow!("User")); }
    let tok = decrypt_token(match &rs[0][0] { DbValue::Str(s) => s, _ => "" }).await?;
    let user = if let DbValue::Str(s) = &rs[0][1] { if !s.is_empty() { decrypt_token(s).await? } else { "me".to_string() } } else { "me".to_string() };
    let body = format!("auth_token={}&value={}&comment={}&requestid={}", tok, val, urlencoding::encode(comment), urlencoding::encode(requestid));
    let res = spin_sdk::http::send(Request::builder().method(Method::POST).uri(format!("https://www.beeminder.com/api/v1/users/{}/goals/{}/datapoints.json", user, slug)).header("content-type", "application/x-www-form-urlencoded").body(body)?).await?;
    if res.status().as_u16() == 422 { return Ok(()); } // 422 usually means duplicate requestid
    if !(200..300).contains(&res.status().as_u16()) { return Err(anyhow::anyhow!("Push fail: {}", res.status())); }
    Ok(())
}

async fn push_to_beeminder(uid: &str, slug: &str, val: f64, comment: &str, conn: &Connection) -> anyhow::Result<()> {'''
)

# 3. Fix handle_walks_post to use idempotent push
content = re.sub(
    r'let miles = \(\(walk\.distance_meters / 1609\.34\) \* 1000\.0\)\.round\(\) / 1000\.0;\s*let _ = push_to_beeminder\(&uid, &goal, miles, "Synced via Spin \(Cumulative\)", &conn\)\.await;',
    r'''let miles = ((walk.distance_meters / 1609.34) * 1000.0).round() / 1000.0;
        let today_ny = chrono::Utc::now().with_timezone(&chrono_tz::America::New_York).format("%Y-%m-%d").to_string();
        let requestid = format!("{}-{}-{}-{}", uid, goal, walk.start_time, walk.distance_meters);
        let _ = push_to_beeminder_idempotent(&uid, &goal, miles, "Synced via Spin (Cumulative)", &requestid, &conn).await;''',
    content
)

with open('mecris-go-spin/sync-service/src/lib.rs', 'w') as f:
    f.write(content)
