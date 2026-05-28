import re

with open('mecris-go-spin/sync-service/src/lib.rs', 'r') as f:
    content = f.read()

# Fix handle_languages_get
content = re.sub(
    r'async fn handle_languages_get\(req: Request\) -> anyhow::Result<Response<String>> \{.*?json_response\(200, &langs\)\s*\}',
    r'''async fn handle_languages_get(req: Request) -> anyhow::Result<Response<String>> {
    let uid = match extract_user_id(req.headers().get("authorization")).await { Some(id) => id, None => return Ok(text_response(401, "Unauthorized")?) };
    let db = match variables::get("db_url").await { Ok(v) if !v.is_empty() => v, _ => variables::get("neon_db_url").await? };
    let conn = Connection::open(&db).await?;
    let rs = conn.query("SELECT language_name, current_reviews, tomorrow_reviews, next_7_days_reviews, daily_rate::FLOAT8, safebuf, derail_risk, pump_multiplier::FLOAT8, beeminder_slug, daily_completions FROM language_stats WHERE user_id = $1", &[ParameterValue::Str(uid)]).await?.collect().await?;
    #[derive(Serialize)] struct LangStat { name: String, current: i32, tomorrow: i32, next_7_days: i32, daily_rate: f64, safebuf: i32, derail_risk: String, pump_multiplier: Option<f64>, daily_completions: i32, goal_met: bool, absolute_target: i32 }
    let mut langs = Vec::new();
    for r in &rs {
        let (name, cur, tom, n7, rate, sb, risk, mult, done) = (match &r[0] { DbValue::Str(s) => s.clone(), _ => continue }, match &r[1] { DbValue::Int32(i) => *i, _ => 0 }, match &r[2] { DbValue::Int32(i) => *i, _ => 0 }, match &r[3] { DbValue::Int32(i) => *i, _ => 0 }, match &r[4] { DbValue::Floating64(f) => *f, _ => 0.0 }, match &r[5] { DbValue::Int32(i) => *i, _ => 0 }, match &r[6] { DbValue::Str(s) => s.clone(), _ => "unknown".to_string() }, match &r[7] { DbValue::Floating64(f) => Some(*f), _ => None }, match &r[9] { DbValue::Int32(i) => *i, _ => 0 });
        let (target, _, met) = calculate_targets(cur, tom, mult.unwrap_or(1.0), done);
        langs.push(LangStat { name, current: cur, tomorrow: tom, next_7_days: n7, daily_rate: rate, safebuf: sb, derail_risk: risk, pump_multiplier: mult, daily_completions: done, goal_met: met, absolute_target: target });
    }
    #[derive(Serialize)] struct LangResp { languages: Vec<LangStat> }
    json_response(200, &LangResp { languages: langs })
}''',
    content, flags=re.DOTALL
)

# Fix handle_budget_get
content = re.sub(
    r'async fn handle_budget_get\(req: Request\) -> anyhow::Result<Response<String>> \{.*?json_response\(200, &budget\)\s*\}',
    r'''async fn handle_budget_get(req: Request) -> anyhow::Result<Response<String>> {
    let uid = match extract_user_id(req.headers().get("authorization")).await { Some(id) => id, None => return Ok(text_response(401, "Unauthorized")?) };
    let db = match variables::get("db_url").await { Ok(v) if !v.is_empty() => v, _ => variables::get("neon_db_url").await? };
    let conn = Connection::open(&db).await?;
    let rs = conn.query("SELECT remaining_budget FROM budget_tracking WHERE user_id = $1 LIMIT 1", &[ParameterValue::Str(uid)]).await?.collect().await?;
    let budget = if rs.is_empty() { 0.0 } else { match &rs[0][0] { DbValue::Floating64(f) => *f, _ => 0.0 } };
    #[derive(Serialize)] struct BudgetResp { remaining_budget: f64 }
    json_response(200, &BudgetResp { remaining_budget: budget })
}''',
    content, flags=re.DOTALL
)

with open('mecris-go-spin/sync-service/src/lib.rs', 'w') as f:
    f.write(content)
