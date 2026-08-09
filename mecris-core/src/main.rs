//! Budget Governor binary - runs on Pi as a cron job or daemon

use clap::Parser;
use mecris_core::budget::{
    BudgetLedger, Budget, BudgetId, ExpiryPolicy, SinkPreference,
    FastModeSink, QualityModeSink, GovernorLoop, GovernorConfig, LedgerTaskPicker,
    TwilioWatcher, TwilioWatcherConfig, budget_routes,
};
use chrono::{Duration, Utc};
use std::sync::Arc;
use tracing::{info, warn, error};
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};
use uuid::Uuid;

#[derive(Parser, Debug)]
#[command(name = "mecris-budget-governor")]
#[command(about = "Mecris Budget Governor - ensures 5/5 spend rate on expiring budgets")]
struct Args {
    /// Database path
    #[arg(long, default_value = "/var/lib/mecris/budget.db")]
    db_path: String,

    /// Run once and exit (for cron)
    #[arg(long)]
    once: bool,

    /// Run as daemon with tick interval (minutes)
    #[arg(long, default_value = "15")]
    interval: u64,

    /// Ollama endpoint
    #[arg(long, default_value = "http://localhost:11434")]
    ollama_endpoint: String,

    /// Ollama model
    #[arg(long, default_value = "gemma:2b")]
    ollama_model: String,

    /// OpenRouter API key (env var OPENROUTER_API_KEY also works)
    #[arg(long, env = "OPENROUTER_API_KEY")]
    openrouter_key: Option<String>,

    /// Quality model
    #[arg(long, default_value = "anthropic/claude-3.5-sonnet")]
    quality_model: String,

    /// Twilio webhook port
    #[arg(long, default_value = "8081")]
    twilio_port: u16,

    /// Budget API port
    #[arg(long, default_value = "8082")]
    api_port: u16,
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    // Initialize tracing
    tracing_subscriber::registry()
        .with(tracing_subscriber::EnvFilter::new(
            std::env::var("RUST_LOG").unwrap_or_else(|_| "info".into()),
        ))
        .with(tracing_subscriber::fmt::layer())
        .init();

    let args = Args::parse();
    info!("Starting Mecris Budget Governor");

    // Initialize ledger
    let ledger = Arc::new(BudgetLedger::new(&args.db_path)?);

    // Initialize sinks
    let fast_sink = FastModeSink::new(&args.ollama_endpoint, &args.ollama_model);
    
    let quality_sink = if let Some(key) = args.openrouter_key {
        QualityModeSink::new(key, &args.quality_model)
    } else {
        warn!("No OpenRouter API key provided - quality mode sink will not be available");
        QualityModeSink::new("dummy", &args.quality_model)
    };

    // Initialize task picker
    let task_picker = Arc::new(LedgerTaskPicker::new(ledger.clone()));

    // Initialize governor
    let config = GovernorConfig {
        tick_interval: Duration::minutes(args.interval as i64),
        max_tasks_per_tick: 3,
        notify_on_cloud_spend: true,
    };

    let governor = GovernorLoop::new(
        ledger.clone(),
        fast_sink,
        quality_sink,
        task_picker,
        config,
    );

    // Initialize Twilio watcher
    let twilio_config = TwilioWatcherConfig {
        webhook_port: args.twilio_port,
        webhook_path: "/webhook/twilio".to_string(),
        low_balance_threshold: 5.0,
        auth_token: None,
    };
    let twilio_watcher = TwilioWatcher::new(ledger.clone(), twilio_config);
    twilio_watcher.start().await?;

    // Start budget API server
    let api_ledger = ledger.clone();
    let api_port = args.api_port;
    tokio::spawn(async move {
        let routes = budget_routes(api_ledger);
        let addr = ([0, 0, 0, 0], api_port);
        info!("Starting budget API on {:?}", addr);
        warp::serve(routes).run(addr).await;
    });

    if args.once {
        info!("Running single governor tick");
        governor.tick().await?;
        info!("Single tick completed");
    } else {
        info!("Starting governor daemon");
        governor.start().await;
        
        // Keep running
        tokio::signal::ctrl_c().await?;
        info!("Shutdown signal received");
        governor.stop().await;
    }

    Ok(())
}