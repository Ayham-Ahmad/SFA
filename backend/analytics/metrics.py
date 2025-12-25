"""
Analytics Metrics Module - DEPRECATED
======================================
This module is deprecated and should not be used.

Logic has been moved to:
- api/main.py (dashboard_metrics endpoint)
- backend/ticker_service.py (live data feed)
- backend/config_service.py (user configuration)

This file is kept only for backwards compatibility.
It will be removed in a future version.
"""

import warnings

def get_key_metrics():
    warnings.warn("get_key_metrics() is deprecated. Use ConfigService instead.", DeprecationWarning)
    return {}

def get_revenue_trend():
    warnings.warn("get_revenue_trend() is deprecated. Use ConfigService instead.", DeprecationWarning)
    return {}

def get_income_trend():
    warnings.warn("get_income_trend() is deprecated. Use ConfigService instead.", DeprecationWarning)
    return {}
