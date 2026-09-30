import pandas as pd
import numpy as np

def compute_kpis(df: pd.DataFrame) -> dict:
    """Compute top-level summary metrics from trade dataframe."""
    if df.empty:
        return {
            "total_deals": 0,
            "total_amount_eok": 0.0,
            "avg_amount": 0.0,
            "avg_pyeong_price": 0.0,
            "max_amount": 0,
            "max_apt": "-",
            "new_high_count": 0
        }
    
    valid_df = df[df["is_cancel"] == 0] if "is_cancel" in df.columns else df
    if valid_df.empty:
        return compute_kpis(pd.DataFrame())
        
    total_deals = int(len(valid_df))
    total_amount_manwon = float(valid_df["deal_amount"].sum())
    total_amount_eok = round(total_amount_manwon / 10000.0, 1) # 만원 -> 억원
    avg_amount = round(float(valid_df["deal_amount"].mean()), 1)
    
    pyeong_prices = valid_df[valid_df["pyeong_price"] > 0]["pyeong_price"]
    avg_pyeong_price = round(float(pyeong_prices.mean()), 1) if not pyeong_prices.empty else 0.0
    
    max_row = valid_df.loc[valid_df["deal_amount"].idxmax()]
    max_amount = int(max_row["deal_amount"])
    max_apt = f"{max_row['sigungu']} {max_row['apt_name']} ({max_row.get('exclusive_area', 0):.1f}m²)"
    
    new_highs_df = detect_new_highs(valid_df)
    new_high_count = len(new_highs_df)
    
    return {
        "total_deals": total_deals,
        "total_amount_eok": total_amount_eok,
        "avg_amount": avg_amount,
        "avg_pyeong_price": avg_pyeong_price,
        "max_amount": max_amount,
        "max_apt": max_apt,
        "new_high_count": new_high_count
    }

def compute_daily_trends(df: pd.DataFrame) -> pd.DataFrame:
    """Group trades by deal_date to get daily volume, average price, and max price."""
    if df.empty:
        return pd.DataFrame(columns=["deal_date", "deal_count", "avg_amount", "max_amount", "avg_pyeong_price"])
    
    valid_df = df[df["is_cancel"] == 0] if "is_cancel" in df.columns else df
    if valid_df.empty:
        return pd.DataFrame(columns=["deal_date", "deal_count", "avg_amount", "max_amount", "avg_pyeong_price"])
        
    grouped = valid_df.groupby("deal_date").agg(
        deal_count=("deal_amount", "count"),
        avg_amount=("deal_amount", "mean"),
        max_amount=("deal_amount", "max"),
        avg_pyeong_price=("pyeong_price", "mean")
    ).reset_index()
    
    grouped["avg_amount"] = grouped["avg_amount"].round(1)
    grouped["avg_pyeong_price"] = grouped["avg_pyeong_price"].round(1)
    return grouped.sort_values("deal_date")

def compute_sido_distribution(df: pd.DataFrame) -> pd.DataFrame:
    """Compute trade volume and average price by sido."""
    if df.empty:
        return pd.DataFrame(columns=["sido", "count", "avg_amount", "avg_pyeong_price"])
        
    valid_df = df[df["is_cancel"] == 0] if "is_cancel" in df.columns else df
    if valid_df.empty:
        return pd.DataFrame(columns=["sido", "count", "avg_amount", "avg_pyeong_price"])
        
    res = valid_df.groupby("sido").agg(
        count=("deal_amount", "count"),
        avg_amount=("deal_amount", "mean"),
        avg_pyeong_price=("pyeong_price", "mean")
    ).reset_index()
    
    res["avg_amount"] = res["avg_amount"].round(1)
    res["avg_pyeong_price"] = res["avg_pyeong_price"].round(1)
    return res.sort_values(by="count", ascending=False)

def compute_pyeong_distribution(df: pd.DataFrame) -> pd.DataFrame:
    """Compute trade distribution and statistics across pyeong categories."""
    order = ["소형", "중소형", "중대형", "대형"]
    if df.empty:
        return pd.DataFrame(columns=["pyeong_category", "count", "avg_amount", "avg_pyeong_price"])
        
    valid_df = df[df["is_cancel"] == 0] if "is_cancel" in df.columns else df
    if valid_df.empty:
        return pd.DataFrame(columns=["pyeong_category", "count", "avg_amount", "avg_pyeong_price"])
        
    res = valid_df.groupby("pyeong_category").agg(
        count=("deal_amount", "count"),
        avg_amount=("deal_amount", "mean"),
        avg_pyeong_price=("pyeong_price", "mean")
    ).reset_index()
    
    res["avg_amount"] = res["avg_amount"].round(1)
    res["avg_pyeong_price"] = res["avg_pyeong_price"].round(1)
    
    # Custom sort by category order
    res["sort_key"] = res["pyeong_category"].map(lambda x: order.index(x) if x in order else 99)
    res = res.sort_values("sort_key").drop(columns=["sort_key"])
    return res

def detect_new_highs(df: pd.DataFrame) -> pd.DataFrame:
    """Detect new all-time high trades for the same complex and exclusive area."""
    if df.empty:
        return pd.DataFrame()
        
    valid_df = df[df["is_cancel"] == 0].copy() if "is_cancel" in df.columns else df.copy()
    if valid_df.empty:
        return pd.DataFrame()
        
    # Sort chronologically
    valid_df = valid_df.sort_values(by=["deal_date", "deal_amount"])
    
    # Key: sido + sigungu + apt_name + rounded exclusive_area
    valid_df["complex_area_key"] = (
        valid_df["sido"] + "_" +
        valid_df["sigungu"] + "_" +
        valid_df["apt_name"] + "_" +
        valid_df["exclusive_area"].round(0).astype(str)
    )
    
    new_high_indices = []
    seen_max_prices: dict[str, int] = {}
    
    for idx, row in valid_df.iterrows():
        key = row["complex_area_key"]
        amt = row["deal_amount"]
        
        if key in seen_max_prices:
            prev_max = seen_max_prices[key]
            if amt > prev_max:
                new_high_indices.append(idx)
                seen_max_prices[key] = amt
        else:
            seen_max_prices[key] = amt
            
    if not new_high_indices:
        return pd.DataFrame()
        
    return valid_df.loc[new_high_indices].sort_values(by="deal_date", ascending=False)

def filter_trades(df: pd.DataFrame, filters: dict) -> pd.DataFrame:
    """Filter trades dataframe by given filter criteria."""
    if df.empty:
        return df
        
    filtered = df.copy()
    
    # Exclude cancellations by default
    if filters.get("exclude_cancel", True) and "is_cancel" in filtered.columns:
        filtered = filtered[filtered["is_cancel"] == 0]
        
    # Sido filter
    if filters.get("sido"):
        sidos = filters["sido"]
        if isinstance(sidos, str):
            sidos = [sidos]
        if "전체" not in sidos and len(sidos) > 0:
            filtered = filtered[filtered["sido"].isin(sidos)]
            
    # Sigungu filter
    if filters.get("sigungu"):
        sigungus = filters["sigungu"]
        if isinstance(sigungus, str):
            sigungus = [sigungus]
        if "전체" not in sigungus and len(sigungus) > 0:
            filtered = filtered[filtered["sigungu"].isin(sigungus)]
            
    # Pyeong category filter
    if filters.get("pyeong_category"):
        cats = filters["pyeong_category"]
        if isinstance(cats, str):
            cats = [cats]
        if "전체" not in cats and len(cats) > 0:
            filtered = filtered[filtered["pyeong_category"].isin(cats)]
            
    # Amount range (만원)
    if "min_amount" in filters and filters["min_amount"] is not None:
        filtered = filtered[filtered["deal_amount"] >= filters["min_amount"]]
    if "max_amount" in filters and filters["max_amount"] is not None:
        filtered = filtered[filtered["deal_amount"] <= filters["max_amount"]]
        
    # Date range
    if filters.get("start_date"):
        filtered = filtered[filtered["deal_date"] >= filters["start_date"]]
    if filters.get("end_date"):
        filtered = filtered[filtered["deal_date"] <= filters["end_date"]]
        
    # Keyword search (apt_name or umd_name)
    if filters.get("keyword"):
        kw = filters["keyword"].strip().lower()
        if kw:
            mask = (
                filtered["apt_name"].str.lower().str.contains(kw, na=False) |
                filtered["sigungu"].str.lower().str.contains(kw, na=False) |
                filtered["umd_name"].str.lower().str.contains(kw, na=False)
            )
            filtered = filtered[mask]
            
    return filtered
