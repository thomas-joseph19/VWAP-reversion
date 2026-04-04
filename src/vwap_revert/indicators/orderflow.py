
import polars as pl
from pathlib import Path

def build_orderflow_delta(df: pl.DataFrame) -> pl.DataFrame:
    """Calculate 1-second and cumulative session delta from tick ‘side’ and ‘size’ data."""
    
    # 1. Map ‘side’ to Aggressor (Buy=1, Sell=-1, None=0)
    # Databento: side=A (Ask/Buy), side=B (Bid/Sell)
    df = df.with_columns(
        pl.when(pl.col("side") == "A").then(pl.col("size").cast(pl.Int64))
        .when(pl.col("side") == "B").then(-pl.col("size").cast(pl.Int64))
        .otherwise(0).alias("delta_sz")
    )
    
    # 2. Cumulative Duration Delta (Session Level)
    df = df.with_columns(
        pl.col("delta_sz").cum_sum().alias("cum_delta_session")
    )
    
    # 3. Rolling 60s Delta (Momentum)
    # We use a 60-second window to detect "Exhaustion" vs "Expansion"
    # Since the data is 1-second BBO, 60 rows = 60 seconds (roughly).
    df = df.with_columns(
        pl.col("delta_sz").rolling_sum(window_size=60).alias("delta_60s")
    )
    
    return df

def detect_delta_divergence(df: pl.DataFrame, lookback_seconds: int = 300) -> pl.Series:
    """Returns True if Price is making new lows/highs but Delta is not."""
    
    # 1. Detect Bullish Divergence (Price falling to Band, Delta rising)
    # 2. Detect Bearish Divergence (Price rising to Band, Delta falling)
    # This will be used in Phase 11 Setup Detection.
    
    # Placeholder for the logic:
    # is_bullish_div = (price < low_300s) & (delta > low_delta_300s)
    pass
