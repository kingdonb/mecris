#!/usr/bin/env python3
"""
Add budget reconciliation table to mecris database
"""
import sqlite3

# Connect to database
conn = sqlite3.connect('mecris_usage.db')

# Add budget reconciliation table
conn.execute('''
CREATE TABLE budget_reconciliation (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reconciliation_date DATE,
    budget_before REAL,
    manual_adjustment REAL,
    budget_after REAL,  
    adjustment_reason TEXT,
    api_usage_tracked REAL,
    manual_plug_amount REAL,
    reconciled_by TEXT DEFAULT 'mcp-workflow',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
''')

print('✅ Created budget_reconciliation table')

# Check current budget to establish baseline
cursor = conn.execute('SELECT remaining_budget, total_budget FROM budget_tracking ORDER BY period_end DESC LIMIT 1')
current = cursor.fetchone()
if current:
    remaining, total = current
    print(f'📊 Current budget: ${remaining:.2f} remaining of ${total:.2f}')

conn.commit()
conn.close()