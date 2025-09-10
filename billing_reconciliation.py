#!/usr/bin/env python3
"""
Billing Reconciliation System - Sync estimates with actual provider billing

This system reconciles our real-time cost estimates with actual billing data
from providers, correcting drift and improving future accuracy.
"""

import logging
import json
from datetime import datetime, timedelta, date
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from virtual_budget_manager import VirtualBudgetManager, Provider
from fetch_groq_usage import fetch_groq_usage

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("reconciliation")

@dataclass
class ReconciliationResult:
    provider: str
    date: str
    estimated_total: float
    actual_total: float
    drift_percentage: float
    records_reconciled: int
    success: bool
    error: Optional[str] = None

class BillingReconciliation:
    def __init__(self):
        self.budget_manager = VirtualBudgetManager()
    
    def reconcile_anthropic(self, target_date: date) -> ReconciliationResult:
        """Reconcile Anthropic usage for a specific date."""
        logger.info(f"Starting Anthropic reconciliation for {target_date}")
        
        try:
            # Get our estimated costs for the date
            estimated_total, usage_records = self._get_estimated_costs(Provider.ANTHROPIC, target_date)
            
            if not usage_records:
                return ReconciliationResult(
                    provider="anthropic",
                    date=target_date.isoformat(),
                    estimated_total=0.0,
                    actual_total=0.0,
                    drift_percentage=0.0,
                    records_reconciled=0,
                    success=True
                )
            
            # Get actual costs from Anthropic API
            actual_total = self._get_anthropic_actual_costs(target_date)
            
            if actual_total is None:
                return ReconciliationResult(
                    provider="anthropic",
                    date=target_date.isoformat(),
                    estimated_total=estimated_total,
                    actual_total=0.0,
                    drift_percentage=0.0,
                    records_reconciled=0,
                    success=False,
                    error="Could not fetch actual Anthropic costs"
                )
            
            # Calculate drift
            drift_percentage = self._calculate_drift_percentage(estimated_total, actual_total)
            
            # Update usage records with actual costs
            records_updated = self._update_usage_records_with_actual_costs(
                Provider.ANTHROPIC, target_date, usage_records, actual_total
            )
            
            # Log reconciliation job
            self._log_reconciliation_job("anthropic", target_date, estimated_total, actual_total, drift_percentage, records_updated)
            
            logger.info(f"Anthropic reconciliation complete: {drift_percentage:.2f}% drift")
            
            return ReconciliationResult(
                provider="anthropic",
                date=target_date.isoformat(),
                estimated_total=estimated_total,
                actual_total=actual_total,
                drift_percentage=drift_percentage,
                records_reconciled=records_updated,
                success=True
            )
            
        except Exception as e:
            logger.error(f"Anthropic reconciliation failed: {e}")
            return ReconciliationResult(
                provider="anthropic",
                date=target_date.isoformat(),
                estimated_total=0.0,
                actual_total=0.0,
                drift_percentage=0.0,
                records_reconciled=0,
                success=False,
                error=str(e)
            )
    
    def reconcile_groq(self, target_date: date) -> ReconciliationResult:
        """Reconcile Groq usage for a specific date."""
        logger.info(f"Starting Groq reconciliation for {target_date}")
        
        try:
            # Get our estimated costs for the date
            estimated_total, usage_records = self._get_estimated_costs(Provider.GROQ, target_date)
            
            if not usage_records:
                return ReconciliationResult(
                    provider="groq",
                    date=target_date.isoformat(),
                    estimated_total=0.0,
                    actual_total=0.0,
                    drift_percentage=0.0,
                    records_reconciled=0,
                    success=True
                )
            
            # Get actual costs from Groq scraper
            actual_total = self._get_groq_actual_costs(target_date)
            
            if actual_total is None:
                return ReconciliationResult(
                    provider="groq",
                    date=target_date.isoformat(),
                    estimated_total=estimated_total,
                    actual_total=0.0,
                    drift_percentage=0.0,
                    records_reconciled=0,
                    success=False,
                    error="Could not fetch actual Groq costs"
                )
            
            # Calculate drift
            drift_percentage = self._calculate_drift_percentage(estimated_total, actual_total)
            
            # Update usage records with actual costs
            records_updated = self._update_usage_records_with_actual_costs(
                Provider.GROQ, target_date, usage_records, actual_total
            )
            
            # Log reconciliation job
            self._log_reconciliation_job("groq", target_date, estimated_total, actual_total, drift_percentage, records_updated)
            
            logger.info(f"Groq reconciliation complete: {drift_percentage:.2f}% drift")
            
            return ReconciliationResult(
                provider="groq",
                date=target_date.isoformat(),
                estimated_total=estimated_total,
                actual_total=actual_total,
                drift_percentage=drift_percentage,
                records_reconciled=records_updated,
                success=True
            )
            
        except Exception as e:
            logger.error(f"Groq reconciliation failed: {e}")
            return ReconciliationResult(
                provider="groq",
                date=target_date.isoformat(),
                estimated_total=0.0,
                actual_total=0.0,
                drift_percentage=0.0,
                records_reconciled=0,
                success=False,
                error=str(e)
            )
    
    def reconcile_all_providers(self, target_date: date) -> List[ReconciliationResult]:
        """Reconcile all providers for a specific date."""
        results = []
        
        # Reconcile Anthropic
        anthro_result = self.reconcile_anthropic(target_date)
        results.append(anthro_result)
        
        # Reconcile Groq
        groq_result = self.reconcile_groq(target_date)
        results.append(groq_result)
        
        return results
    
    def daily_reconciliation(self, days_back: int = 1) -> List[ReconciliationResult]:
        """Run daily reconciliation for recent days."""
        results = []
        
        for i in range(days_back):
            target_date = date.today() - timedelta(days=i+1)  # Skip today, start with yesterday
            logger.info(f"Running daily reconciliation for {target_date}")
            
            daily_results = self.reconcile_all_providers(target_date)
            results.extend(daily_results)
        
        return results
    
    def _get_estimated_costs(self, provider: Provider, target_date: date) -> Tuple[float, List[Dict]]:
        """Get estimated costs for a provider on a specific date."""
        import sqlite3
        
        with sqlite3.connect(self.budget_manager.db_path) as conn:
            cursor = conn.execute("""
                SELECT id, estimated_cost FROM provider_usage 
                WHERE provider = ? AND DATE(timestamp) = ? AND reconciled = FALSE
            """, (provider.value, target_date.isoformat()))
            
            records = cursor.fetchall()
            total_estimated = sum(row[1] for row in records)
            usage_records = [{"id": row[0], "estimated_cost": row[1]} for row in records]
            
            return total_estimated, usage_records
    
    def _get_anthropic_actual_costs(self, target_date: date) -> Optional[float]:
        """Get actual costs from Anthropic API for a specific date."""
        try:
            from scripts.anthropic_cost_tracker import AnthropicCostTracker
            
            tracker = AnthropicCostTracker()
            
            # Convert date to datetime range
            start_time = datetime.combine(target_date, datetime.min.time()).replace(tzinfo=None)
            end_time = start_time + timedelta(days=1)
            
            # Get cost data (daily buckets only for cost API)
            cost_data = tracker.get_cost(start_time, end_time)
            
            # Extract total cost for the day
            total_cost = 0.0
            for bucket in cost_data.get('data', []):
                for result in bucket.get('results', []):
                    if 'cost' in result:
                        total_cost += float(result['cost'])
            
            return total_cost if total_cost > 0 else None
            
        except Exception as e:
            logger.error(f"Failed to get Anthropic actual costs: {e}")
            return None
    
    def _get_groq_actual_costs(self, target_date: date) -> Optional[float]:
        """Get actual costs from Groq scraper for a specific date."""
        try:
            usage_data = fetch_groq_usage()
            
            if not usage_data.get("success"):
                logger.warning(f"Groq usage fetch failed: {usage_data.get('error')}")
                return None
            
            # Extract cost data from scraped results
            # This is rough since Groq typically shows monthly totals
            data = usage_data.get("data", {})
            
            # Try to parse monthly usage and estimate daily
            monthly_cost = 0.0
            
            # Look for dollar amounts in the scraped data
            for key, value in data.items():
                if isinstance(value, str) and '$' in value:
                    try:
                        # Extract dollar amount from string like "$1.06" or "$1.06 this month"
                        import re
                        amounts = re.findall(r'\$(\d+\.?\d*)', value)
                        if amounts:
                            monthly_cost = max(monthly_cost, float(amounts[0]))
                    except:
                        continue
            
            if monthly_cost > 0:
                # Rough daily estimate (monthly cost / days in month)
                days_in_month = target_date.replace(day=28).day
                if target_date.month == 2:
                    days_in_month = 28
                elif target_date.month in [1, 3, 5, 7, 8, 10, 12]:
                    days_in_month = 31
                else:
                    days_in_month = 30
                
                daily_estimate = monthly_cost / days_in_month
                logger.info(f"Groq daily cost estimate: ${daily_estimate:.4f} (from monthly ${monthly_cost:.2f})")
                return daily_estimate
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get Groq actual costs: {e}")
            return None
    
    def _calculate_drift_percentage(self, estimated: float, actual: float) -> float:
        """Calculate drift percentage between estimated and actual costs."""
        if actual == 0:
            return 0.0 if estimated == 0 else 100.0
        
        return ((estimated - actual) / actual) * 100.0
    
    def _update_usage_records_with_actual_costs(self, provider: Provider, target_date: date, 
                                               usage_records: List[Dict], total_actual: float) -> int:
        """Update usage records with reconciled actual costs."""
        if not usage_records or total_actual <= 0:
            return 0
        
        # Calculate scaling factor to distribute actual cost across records
        total_estimated = sum(record["estimated_cost"] for record in usage_records)
        if total_estimated <= 0:
            return 0
        
        scale_factor = total_actual / total_estimated
        
        import sqlite3
        records_updated = 0
        
        with sqlite3.connect(self.budget_manager.db_path) as conn:
            for record in usage_records:
                actual_cost = record["estimated_cost"] * scale_factor
                
                conn.execute("""
                    UPDATE provider_usage 
                    SET actual_cost = ?, reconciled = TRUE 
                    WHERE id = ?
                """, (actual_cost, record["id"]))
                
                records_updated += 1
        
        return records_updated
    
    def _log_reconciliation_job(self, provider: str, target_date: date, estimated_total: float,
                               actual_total: float, drift_percentage: float, records_reconciled: int):
        """Log a reconciliation job for tracking accuracy over time."""
        import sqlite3
        
        with sqlite3.connect(self.budget_manager.db_path) as conn:
            conn.execute("""
                INSERT INTO reconciliation_jobs 
                (provider, job_date, estimated_total, actual_total, drift_percentage, records_reconciled, reconciled_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                provider, 
                target_date.isoformat(),
                estimated_total,
                actual_total,
                drift_percentage,
                records_reconciled,
                datetime.now().isoformat()
            ))
    
    def get_reconciliation_summary(self, days: int = 7) -> Dict:
        """Get reconciliation accuracy summary for recent days."""
        cutoff_date = (date.today() - timedelta(days=days)).isoformat()
        
        import sqlite3
        with sqlite3.connect(self.budget_manager.db_path) as conn:
            # Summary by provider
            cursor = conn.execute("""
                SELECT 
                    provider,
                    COUNT(*) as jobs_count,
                    AVG(ABS(drift_percentage)) as avg_abs_drift,
                    AVG(drift_percentage) as avg_drift,
                    SUM(estimated_total) as total_estimated,
                    SUM(actual_total) as total_actual
                FROM reconciliation_jobs 
                WHERE job_date > ?
                GROUP BY provider
            """, (cutoff_date,))
            
            provider_summary = {}
            for row in cursor.fetchall():
                provider_summary[row[0]] = {
                    "jobs_count": row[1],
                    "avg_abs_drift_pct": round(row[2] or 0, 2),
                    "avg_drift_pct": round(row[3] or 0, 2),
                    "total_estimated": round(row[4] or 0, 4),
                    "total_actual": round(row[5] or 0, 4)
                }
            
            # Recent jobs
            cursor = conn.execute("""
                SELECT provider, job_date, drift_percentage, records_reconciled, reconciled_at
                FROM reconciliation_jobs 
                WHERE job_date > ?
                ORDER BY reconciled_at DESC
                LIMIT 20
            """, (cutoff_date,))
            
            recent_jobs = [
                {
                    "provider": row[0],
                    "job_date": row[1],
                    "drift_percentage": round(row[2], 2),
                    "records_reconciled": row[3],
                    "reconciled_at": row[4]
                }
                for row in cursor.fetchall()
            ]
        
        return {
            "period_days": days,
            "provider_summary": provider_summary,
            "recent_jobs": recent_jobs,
            "overall_accuracy": {
                "avg_abs_drift": sum(p["avg_abs_drift_pct"] for p in provider_summary.values()) / len(provider_summary) if provider_summary else 0
            }
        }

def run_daily_reconciliation():
    """Main function for running daily reconciliation."""
    reconciler = BillingReconciliation()
    results = reconciler.daily_reconciliation(days_back=2)  # Reconcile yesterday and day before
    
    print("=== Daily Reconciliation Results ===")
    for result in results:
        status = "✅ SUCCESS" if result.success else "❌ FAILED"
        print(f"{status} {result.provider} {result.date}: {result.drift_percentage:.2f}% drift")
        if result.error:
            print(f"  Error: {result.error}")
    
    # Print accuracy summary
    summary = reconciler.get_reconciliation_summary(7)
    print(f"\n=== 7-Day Accuracy Summary ===")
    for provider, stats in summary["provider_summary"].items():
        print(f"{provider}: {stats['avg_abs_drift_pct']:.2f}% avg drift ({stats['jobs_count']} jobs)")

if __name__ == "__main__":
    run_daily_reconciliation()