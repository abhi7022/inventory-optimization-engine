#!/usr/bin/env python3
"""
test_app.py - Standalone Python script to print system information
and calculate safety stock for inventory management.
"""

import sys
import os
import platform
import math
import argparse
from datetime import datetime

# Common Z-scores for standard service levels (Normal Distribution)
SERVICE_LEVEL_Z = {
    85.0: 1.04,
    90.0: 1.28,
    95.0: 1.645,
    97.5: 1.96,
    98.0: 2.05,
    99.0: 2.33,
    99.9: 3.09,
}

def get_z_score(service_level_pct: float) -> float:
    """Returns Z-score for service level using lookup or normal approximation."""
    if service_level_pct in SERVICE_LEVEL_Z:
        return SERVICE_LEVEL_Z[service_level_pct]
    p = service_level_pct / 100.0
    if not (0.0 < p < 1.0):
        raise ValueError("Service level must be between 0 and 100.")
    q = 1.0 - p if p > 0.5 else p
    t = math.sqrt(-2.0 * math.log(q))
    c0, c1, c2 = 2.515517, 0.802853, 0.010328
    d1, d2, d3 = 1.432788, 0.189269, 0.001308
    z = t - ((c2 * t + c1) * t + c0) / (((d3 * t + d2) * t + d1) * t + 1.0)
    return round(z if p >= 0.5 else -z, 3)

def print_system_info():
    """Prints system and environment information."""
    sep = "=" * 60
    print(sep)
    print(" SYSTEM INFORMATION ".center(60, " "))
    print(sep)
    print(f" Timestamp        : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f" Operating System : {platform.system()} {platform.release()} (v{platform.version()})")
    print(f" Architecture     : {platform.machine()} ({platform.architecture()[0]})")
    print(f" Processor        : {platform.processor() or 'N/A'}")
    print(f" Hostname         : {platform.node()}")
    print(f" Python Version   : {platform.python_version()} ({platform.python_implementation()})")
    print(f" Python Executable: {sys.executable}")
    print(f" Working Directory: {os.getcwd()}")
    print(sep)
    print()

def calculate_safety_stock(lead_time: float, std_dev_demand: float, service_level: float = 95.0) -> dict:
    """Calculates statistical safety stock: SS = Z * sigma_D * sqrt(L)."""
    z = get_z_score(service_level)
    std_dev_lt = std_dev_demand * math.sqrt(lead_time)
    ss = z * std_dev_lt
    return {
        "service_level": service_level,
        "z_score": z,
        "std_dev_over_lt": round(std_dev_lt, 2),
        "safety_stock_exact": round(ss, 2),
        "safety_stock_units": math.ceil(ss),
    }

def calculate_heuristic_safety_stock(max_demand: float, avg_demand: float, max_lt: float, avg_lt: float) -> int:
    """Calculates safety stock using heuristic: (Max Demand * Max LT) - (Avg Demand * Avg LT)."""
    ss = (max_demand * max_lt) - (avg_demand * avg_lt)
    return math.ceil(max(0.0, ss))

def print_safety_stock_analysis(lead_time: float, avg_demand: float, std_demand: float,
                                service_level: float, max_demand: float, max_lt: float):
    """Executes and prints safety stock calculations."""
    sep = "=" * 60
    sub_sep = "-" * 60
    print(sep)
    print(" SAFETY STOCK CALCULATION ".center(60, " "))
    print(sep)

    stat = calculate_safety_stock(lead_time, std_demand, service_level)
    rop = (avg_demand * lead_time) + stat["safety_stock_units"]

    print("Method 1: Statistical Model (Normal Distribution)")
    print(sub_sep)
    print(f"  Inputs:")
    print(f"    - Average Demand per Period (D) : {avg_demand:.1f} units")
    print(f"    - Std Dev of Demand (sigma_D)   : {std_demand:.1f} units")
    print(f"    - Average Lead Time (L)         : {lead_time:.1f} periods")
    print(f"    - Service Level                 : {service_level:.1f}% (Z = {stat['z_score']})")
    print(f"  Formula: SS = Z * sigma_D * sqrt(L)")
    print(f"  Results:")
    print(f"    -> Exact Safety Stock           : {stat['safety_stock_exact']:.2f} units")
    print(f"    -> Recommended Safety Stock     : {stat['safety_stock_units']} units")
    print(f"    -> Reorder Point (ROP = D*L+SS) : {rop:.0f} units")
    print()

    heur_ss = calculate_heuristic_safety_stock(max_demand, avg_demand, max_lt, lead_time)
    print("Method 2: Max / Average Heuristic Model")
    print(sub_sep)
    print(f"  Inputs:")
    print(f"    - Demand (Max / Avg)            : {max_demand:.1f} / {avg_demand:.1f} units")
    print(f"    - Lead Time (Max / Avg)         : {max_lt:.1f} / {lead_time:.1f} periods")
    print(f"  Formula: SS = (Max Demand * Max LT) - (Avg Demand * Avg LT)")
    print(f"  Results:")
    print(f"    -> Recommended Safety Stock     : {heur_ss} units")
    print(sep)

def parse_args():
    parser = argparse.ArgumentParser(description="System Info & Safety Stock Calculator")
    parser.add_argument("--lead-time", "-l", type=float, default=7.0, help="Lead time in periods (default: 7.0)")
    parser.add_argument("--avg-demand", "-d", type=float, default=50.0, help="Average demand per period (default: 50.0)")
    parser.add_argument("--std-demand", "-s", type=float, default=10.0, help="Std dev of demand (default: 10.0)")
    parser.add_argument("--service-level", "-z", type=float, default=95.0, help="Service level %% (default: 95.0)")
    parser.add_argument("--max-demand", type=float, default=75.0, help="Max demand per period (default: 75.0)")
    parser.add_argument("--max-lt", type=float, default=10.0, help="Max lead time (default: 10.0)")
    return parser.parse_args()

def main():
    args = parse_args()
    print_system_info()
    print_safety_stock_analysis(
        lead_time=args.lead_time,
        avg_demand=args.avg_demand,
        std_demand=args.std_demand,
        service_level=args.service_level,
        max_demand=args.max_demand,
        max_lt=args.max_lt
    )

if __name__ == "__main__":
    main()
