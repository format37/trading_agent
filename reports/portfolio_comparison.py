#!/usr/bin/env python3
"""
Portfolio Comparison: Actual Trading vs. BTC+ETH+USDT Buy-and-Hold

Compares actual trading agent performance against a hypothetical equal-weight
portfolio of BTC (33.3%), ETH (33.3%), and USDT (33.3%) with no rebalancing.

This script:
1. Fetches historical BTC/ETH prices for the last 30 days
2. Reconstructs actual portfolio equity from account snapshots
3. Detects capitalization events (deposits)
4. Calculates hypothetical portfolio with same capital timing
5. Generates comparison visualization and metrics

Author: Trading Agent Analysis
Date: 2025-10-29
"""

import os
import sys
import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from pathlib import Path
from glob import glob

# ============================================================================
# CONFIGURATION
# ============================================================================

# Portfolio allocation for hypothetical portfolio
PORTFOLIO_WEIGHTS = {
    'BTC': 0.333,
    'ETH': 0.333,
    'USDT': 0.334  # Slight adjustment to sum to 1.0
}

# Analysis period (days)
LOOKBACK_DAYS = 30

# Data paths
DATA_DIR = Path('../data/mcp-binance')
OUTPUT_DIR = Path('./')

# Deposit detection threshold (minimum value change to consider as deposit)
DEPOSIT_THRESHOLD_USD = 50.0

# Visualization settings
FIGURE_SIZE = (12, 7)
DPI = 100

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def print_section(title):
    """Print formatted section header"""
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}\n")

def load_account_snapshots():
    """Load all account snapshot files and sort by timestamp"""
    print_section("Loading Account Snapshots")

    snapshot_files = sorted(glob(str(DATA_DIR / 'account_*.csv')))

    if not snapshot_files:
        raise FileNotFoundError(f"No account snapshot files found in {DATA_DIR}")

    print(f"Found {len(snapshot_files)} account snapshot files")

    snapshots = []

    for file_path in snapshot_files:
        try:
            # Extract timestamp from filename if available, otherwise use file modification time
            file_mtime = os.path.getmtime(file_path)
            timestamp = datetime.fromtimestamp(file_mtime)

            # Read snapshot data
            df = pd.read_csv(file_path)

            # Calculate total portfolio value
            if 'value_usdt' in df.columns:
                total_value = df['value_usdt'].sum()
            else:
                # Fallback: assume 'total' column exists and convert manually
                print(f"Warning: 'value_usdt' column not found in {file_path}")
                continue

            snapshots.append({
                'timestamp': timestamp,
                'total_value_usdt': total_value,
                'file': os.path.basename(file_path),
                'assets': df.to_dict('records')
            })

        except Exception as e:
            print(f"Warning: Could not load {file_path}: {e}")
            continue

    # Sort by timestamp
    snapshots.sort(key=lambda x: x['timestamp'])

    print(f"Loaded {len(snapshots)} valid snapshots")
    print(f"Date range: {snapshots[0]['timestamp'].strftime('%Y-%m-%d')} to {snapshots[-1]['timestamp'].strftime('%Y-%m-%d')}")

    return snapshots

def detect_deposits(snapshots):
    """Detect capitalization events (deposits) from account snapshots"""
    print_section("Detecting Capitalization Events")

    deposits = []

    for i in range(1, len(snapshots)):
        prev_value = snapshots[i-1]['total_value_usdt']
        curr_value = snapshots[i]['total_value_usdt']
        value_change = curr_value - prev_value

        time_diff = snapshots[i]['timestamp'] - snapshots[i-1]['timestamp']

        # If value increases significantly and time gap suggests no trading impact
        # we consider it a deposit
        if value_change > DEPOSIT_THRESHOLD_USD:
            deposits.append({
                'timestamp': snapshots[i]['timestamp'],
                'amount_usdt': value_change,
                'prev_value': prev_value,
                'new_value': curr_value
            })

            print(f"Deposit detected: {snapshots[i]['timestamp'].strftime('%Y-%m-%d %H:%M')} - "
                  f"${value_change:,.2f} (${prev_value:,.2f} → ${curr_value:,.2f})")

    total_deposits = sum(d['amount_usdt'] for d in deposits)
    print(f"\nTotal capitalization events: {len(deposits)}")
    print(f"Total deposited: ${total_deposits:,.2f}")

    return deposits

def fetch_historical_prices():
    """Fetch historical BTC and ETH prices for the last 30 days

    This function will use Binance MCP tools to get historical price data.
    For simplicity, we'll use ticker data and trade history as proxies.
    """
    print_section("Fetching Historical Prices")

    # Calculate date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=LOOKBACK_DAYS)

    print(f"Fetching prices from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")

    # Try to load from existing ticker files or trade history
    prices = {
        'BTC': {},
        'ETH': {}
    }

    # Load from trade history files as price reference points
    for symbol, asset in [('BTCUSDT', 'BTC'), ('ETHUSDT', 'ETH')]:
        trade_files = glob(str(DATA_DIR / f'trade_history_{symbol}_*.csv'))

        if trade_files:
            # Use most recent trade history file
            trade_file = sorted(trade_files)[-1]
            trades_df = pd.read_csv(trade_file)

            if 'time' in trades_df.columns and 'price' in trades_df.columns:
                # Convert time to datetime
                trades_df['time'] = pd.to_datetime(trades_df['time'])

                # Group by date and get average price
                trades_df['date'] = trades_df['time'].dt.date
                daily_prices = trades_df.groupby('date')['price'].mean()

                for date, price in daily_prices.items():
                    prices[asset][pd.Timestamp(date)] = price

                print(f"Loaded {len(daily_prices)} price points for {asset} from trade history")

    # Fill missing dates with last known price (simple forward fill)
    date_range = pd.date_range(start=start_date, end=end_date, freq='D')

    for asset in ['BTC', 'ETH']:
        if not prices[asset]:
            print(f"Warning: No price data found for {asset}, will use placeholder")
            continue

        # Convert to series and forward fill
        price_series = pd.Series(prices[asset]).sort_index()
        price_series = price_series.reindex(date_range, method='ffill')
        prices[asset] = price_series.to_dict()

    return prices, start_date, end_date

def build_actual_equity_curve(snapshots, start_date, end_date):
    """Build actual portfolio equity curve from snapshots"""
    print_section("Building Actual Portfolio Equity Curve")

    # Filter snapshots to date range
    snapshots_in_range = [
        s for s in snapshots
        if start_date <= s['timestamp'] <= end_date
    ]

    if not snapshots_in_range:
        print("Warning: No snapshots in date range, using all available snapshots")
        snapshots_in_range = snapshots

    # Create daily equity values
    equity_data = []

    for snapshot in snapshots_in_range:
        equity_data.append({
            'date': snapshot['timestamp'].date(),
            'equity_usdt': snapshot['total_value_usdt']
        })

    equity_df = pd.DataFrame(equity_data)

    # Group by date and take last value of each day
    equity_df = equity_df.groupby('date').last().reset_index()
    equity_df['date'] = pd.to_datetime(equity_df['date'])
    equity_df = equity_df.sort_values('date')

    print(f"Built equity curve with {len(equity_df)} data points")
    print(f"Initial equity: ${equity_df.iloc[0]['equity_usdt']:,.2f}")
    print(f"Final equity: ${equity_df.iloc[-1]['equity_usdt']:,.2f}")

    return equity_df

def build_hypothetical_portfolio(prices, deposits, start_date, end_date, initial_capital):
    """Build hypothetical BTC+ETH+USDT portfolio equity curve"""
    print_section("Building Hypothetical Portfolio (33% BTC, 33% ETH, 33% USDT)")

    # Initialize portfolio at start date
    btc_prices = prices['BTC']
    eth_prices = prices['ETH']

    # Get starting prices
    start_ts = pd.Timestamp(start_date)

    # Find closest price to start date
    btc_start_price = None
    eth_start_price = None

    for ts in sorted(btc_prices.keys()):
        if ts >= start_ts:
            btc_start_price = btc_prices[ts]
            break

    for ts in sorted(eth_prices.keys()):
        if ts >= start_ts:
            eth_start_price = eth_prices[ts]
            break

    if btc_start_price is None or eth_start_price is None:
        # Use first available prices
        btc_start_price = list(btc_prices.values())[0]
        eth_start_price = list(eth_prices.values())[0]

    print(f"Initial capital: ${initial_capital:,.2f}")
    print(f"Starting prices: BTC=${btc_start_price:,.2f}, ETH=${eth_start_price:,.2f}")

    # Calculate initial holdings
    btc_amount = (initial_capital * PORTFOLIO_WEIGHTS['BTC']) / btc_start_price
    eth_amount = (initial_capital * PORTFOLIO_WEIGHTS['ETH']) / eth_start_price
    usdt_amount = initial_capital * PORTFOLIO_WEIGHTS['USDT']

    print(f"Initial holdings:")
    print(f"  BTC: {btc_amount:.8f} (${initial_capital * PORTFOLIO_WEIGHTS['BTC']:,.2f})")
    print(f"  ETH: {eth_amount:.8f} (${initial_capital * PORTFOLIO_WEIGHTS['ETH']:,.2f})")
    print(f"  USDT: ${usdt_amount:,.2f}")

    # Build daily equity curve
    date_range = pd.date_range(start=start_date, end=end_date, freq='D')
    equity_data = []

    # Create deposit lookup by date (not datetime)
    deposit_by_date = {}
    for d in deposits:
        deposit_date = d['timestamp'].date()
        if deposit_date not in deposit_by_date:
            deposit_by_date[deposit_date] = 0.0
        deposit_by_date[deposit_date] += d['amount_usdt']

    for date in date_range:
        # Apply deposits on this date
        date_key = date.date()
        if date_key in deposit_by_date:
            deposit_amount = deposit_by_date[date_key]
            print(f"Applying deposit on {date.strftime('%Y-%m-%d')}: ${deposit_amount:,.2f}")

            # Get current prices for this date
            current_btc_price = None
            current_eth_price = None

            # Find closest available price
            for price_date in sorted(btc_prices.keys()):
                if price_date.date() >= date_key:
                    current_btc_price = btc_prices[price_date]
                    break
            if current_btc_price is None:
                current_btc_price = btc_start_price

            for price_date in sorted(eth_prices.keys()):
                if price_date.date() >= date_key:
                    current_eth_price = eth_prices[price_date]
                    break
            if current_eth_price is None:
                current_eth_price = eth_start_price

            # Add to holdings according to allocation
            btc_amount += (deposit_amount * PORTFOLIO_WEIGHTS['BTC']) / current_btc_price
            eth_amount += (deposit_amount * PORTFOLIO_WEIGHTS['ETH']) / current_eth_price
            usdt_amount += deposit_amount * PORTFOLIO_WEIGHTS['USDT']

        # Calculate portfolio value for this date
        # Find closest available prices
        btc_price = btc_start_price
        eth_price = eth_start_price

        for price_date in sorted(btc_prices.keys()):
            if price_date.date() <= date.date():
                btc_price = btc_prices[price_date]
            else:
                break

        for price_date in sorted(eth_prices.keys()):
            if price_date.date() <= date.date():
                eth_price = eth_prices[price_date]
            else:
                break

        portfolio_value = (
            btc_amount * btc_price +
            eth_amount * eth_price +
            usdt_amount
        )

        equity_data.append({
            'date': date,
            'equity_usdt': portfolio_value,
            'btc_value': btc_amount * btc_price,
            'eth_value': eth_amount * eth_price,
            'usdt_value': usdt_amount
        })

    equity_df = pd.DataFrame(equity_data)

    print(f"\nFinal holdings:")
    print(f"  BTC: {btc_amount:.8f} (${equity_data[-1]['btc_value']:,.2f})")
    print(f"  ETH: {eth_amount:.8f} (${equity_data[-1]['eth_value']:,.2f})")
    print(f"  USDT: ${usdt_amount:,.2f}")
    print(f"Final equity: ${equity_df.iloc[-1]['equity_usdt']:,.2f}")

    return equity_df

def calculate_metrics(actual_df, hypothetical_df, initial_capital, total_deposits):
    """Calculate comparison metrics"""
    print_section("Performance Metrics")

    # Align dataframes by date
    merged = pd.merge(
        actual_df[['date', 'equity_usdt']].rename(columns={'equity_usdt': 'actual'}),
        hypothetical_df[['date', 'equity_usdt']].rename(columns={'equity_usdt': 'hypothetical'}),
        on='date',
        how='outer'
    ).sort_values('date')

    # Forward fill missing values, then backfill to handle leading NaNs
    merged = merged.ffill().bfill()

    # Calculate returns - use first non-NaN value for initial
    actual_series = merged['actual'].dropna()
    hypo_series = merged['hypothetical'].dropna()

    if len(actual_series) == 0 or len(hypo_series) == 0:
        raise ValueError("Not enough data to calculate metrics")

    actual_initial = actual_series.iloc[0]
    actual_final = actual_series.iloc[-1]

    hypo_initial = hypo_series.iloc[0]
    hypo_final = hypo_series.iloc[-1]

    # Calculate total capital invested (initial + deposits)
    total_invested = initial_capital + total_deposits

    # Calculate TRUE returns based on total capital invested
    actual_return = ((actual_final - total_invested) / total_invested) * 100
    hypo_return = ((hypo_final - total_invested) / total_invested) * 100

    # Maximum drawdown
    actual_peak = merged['actual'].expanding().max()
    actual_dd = ((merged['actual'] - actual_peak) / actual_peak * 100).min()

    hypo_peak = merged['hypothetical'].expanding().max()
    hypo_dd = ((merged['hypothetical'] - hypo_peak) / hypo_peak * 100).min()

    metrics = {
        'actual': {
            'initial': actual_initial,
            'final': actual_final,
            'total_invested': total_invested,
            'return_pct': actual_return,
            'max_drawdown_pct': actual_dd,
            'profit_loss': actual_final - total_invested
        },
        'hypothetical': {
            'initial': hypo_initial,
            'final': hypo_final,
            'total_invested': total_invested,
            'return_pct': hypo_return,
            'max_drawdown_pct': hypo_dd,
            'profit_loss': hypo_final - total_invested
        }
    }

    # Print metrics
    print(f"CAPITAL INVESTED:")
    print(f"  Initial Capital: ${initial_capital:,.2f}")
    print(f"  Total Deposits: ${total_deposits:,.2f}")
    print(f"  Total Invested: ${total_invested:,.2f}")

    print("\nACTUAL TRADING PERFORMANCE:")
    print(f"  Final Equity: ${metrics['actual']['final']:,.2f}")
    print(f"  Return on Investment: {metrics['actual']['return_pct']:.2f}%")
    print(f"  Profit/Loss: ${metrics['actual']['profit_loss']:,.2f}")
    print(f"  Max Drawdown: {metrics['actual']['max_drawdown_pct']:.2f}%")

    print("\nHYPOTHETICAL BUY-AND-HOLD (BTC+ETH+USDT):")
    print(f"  Final Equity: ${metrics['hypothetical']['final']:,.2f}")
    print(f"  Return on Investment: {metrics['hypothetical']['return_pct']:.2f}%")
    print(f"  Profit/Loss: ${metrics['hypothetical']['profit_loss']:,.2f}")
    print(f"  Max Drawdown: {metrics['hypothetical']['max_drawdown_pct']:.2f}%")

    # Performance difference
    outperformance = metrics['actual']['return_pct'] - metrics['hypothetical']['return_pct']
    print(f"\nOUTPERFORMANCE: {outperformance:+.2f}%")

    if outperformance > 0:
        print("✓ Trading agent outperformed buy-and-hold")
    else:
        print("✗ Trading agent underperformed buy-and-hold")

    return metrics, merged

def create_visualization(merged_df, metrics):
    """Create comparison visualization"""
    print_section("Generating Visualization")

    fig, ax = plt.subplots(figsize=FIGURE_SIZE, dpi=DPI)

    # Plot equity curves
    ax.plot(merged_df['date'], merged_df['actual'],
            label='Actual Trading', linewidth=2, color='#2E86AB')
    ax.plot(merged_df['date'], merged_df['hypothetical'],
            label='BTC+ETH+USDT Buy-Hold', linewidth=2, color='#A23B72', linestyle='--')

    # Formatting
    ax.set_xlabel('Date', fontsize=11, fontweight='bold')
    ax.set_ylabel('Portfolio Value (USDT)', fontsize=11, fontweight='bold')
    ax.set_title('Portfolio Comparison: Trading Agent vs. Buy-and-Hold Strategy',
                 fontsize=14, fontweight='bold', pad=20)
    ax.legend(fontsize=10, loc='best')
    ax.grid(True, alpha=0.3, linestyle=':')

    # Format y-axis as currency
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.0f}'))

    # Add metrics table
    outperformance = metrics['actual']['return_pct'] - metrics['hypothetical']['return_pct']
    metrics_text = (
        f"CAPITAL INVESTED: ${metrics['actual']['total_invested']:,.2f}\n"
        f"\n"
        f"ACTUAL TRADING\n"
        f"  Final: ${metrics['actual']['final']:,.2f}\n"
        f"  Return: {metrics['actual']['return_pct']:+.2f}%\n"
        f"  P/L: ${metrics['actual']['profit_loss']:+,.2f}\n"
        f"  Max DD: {metrics['actual']['max_drawdown_pct']:.2f}%\n"
        f"\n"
        f"BUY-AND-HOLD\n"
        f"  Final: ${metrics['hypothetical']['final']:,.2f}\n"
        f"  Return: {metrics['hypothetical']['return_pct']:+.2f}%\n"
        f"  P/L: ${metrics['hypothetical']['profit_loss']:+,.2f}\n"
        f"  Max DD: {metrics['hypothetical']['max_drawdown_pct']:.2f}%\n"
        f"\n"
        f"Outperformance: {outperformance:+.2f}%"
    )

    # Add text box
    props = dict(boxstyle='round', facecolor='wheat', alpha=0.8)
    ax.text(0.02, 0.88, metrics_text, transform=ax.transAxes, fontsize=9,
            verticalalignment='top', bbox=props, family='monospace')

    plt.tight_layout()

    # Save figure
    output_path = OUTPUT_DIR / 'portfolio_comparison.png'
    plt.savefig(output_path, dpi=DPI, bbox_inches='tight')
    print(f"Saved visualization to: {output_path}")

    return fig

def save_results(merged_df, metrics):
    """Save results to CSV"""
    print_section("Saving Results")

    # Save equity curves
    output_csv = OUTPUT_DIR / 'portfolio_comparison.csv'
    merged_df.to_csv(output_csv, index=False)
    print(f"Saved equity curves to: {output_csv}")

    # Save metrics as JSON
    metrics_json = OUTPUT_DIR / 'portfolio_comparison_metrics.json'
    with open(metrics_json, 'w') as f:
        # Convert to serializable format
        metrics_serializable = {
            'actual': {k: float(v) for k, v in metrics['actual'].items()},
            'hypothetical': {k: float(v) for k, v in metrics['hypothetical'].items()},
            'generated_at': datetime.now().isoformat()
        }
        json.dump(metrics_serializable, f, indent=2)
    print(f"Saved metrics to: {metrics_json}")

# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Main execution flow"""
    print("\n" + "="*70)
    print("  PORTFOLIO COMPARISON ANALYSIS")
    print("  Actual Trading vs. BTC+ETH+USDT Buy-and-Hold")
    print("="*70)

    try:
        # 1. Load account snapshots
        snapshots = load_account_snapshots()

        # 2. Detect deposits
        deposits = detect_deposits(snapshots)

        # 3. Fetch historical prices
        prices, start_date, end_date = fetch_historical_prices()

        # 4. Build actual equity curve
        actual_equity = build_actual_equity_curve(snapshots, start_date, end_date)

        # 5. Build hypothetical portfolio
        initial_capital = actual_equity.iloc[0]['equity_usdt']
        hypothetical_equity = build_hypothetical_portfolio(
            prices, deposits, start_date, end_date, initial_capital
        )

        # 6. Calculate metrics
        total_deposits = sum(d['amount_usdt'] for d in deposits)
        metrics, merged = calculate_metrics(actual_equity, hypothetical_equity, initial_capital, total_deposits)

        # 7. Create visualization
        create_visualization(merged, metrics)

        # 8. Save results
        save_results(merged, metrics)

        print_section("Analysis Complete")
        print("All results saved to examples/ directory")

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0

if __name__ == '__main__':
    sys.exit(main())
