"""Аналитические формулы. Единица потерь: млн USD на годовой сценарий."""

from math import exp, prod, sqrt

import numpy as np


def series_reliability(reliabilities):
    values = tuple(float(x) for x in reliabilities)
    if not values or any(not 0 <= x <= 1 for x in values):
        raise ValueError("Reliabilities must lie in [0,1]")
    return prod(values)


def frechet_bounds(ra, rb):
    if not 0 <= ra <= 1 or not 0 <= rb <= 1:
        raise ValueError("Reliabilities must lie in [0,1]")
    qa, qb = 1 - ra, 1 - rb
    scale = sqrt(ra * qa * rb * qb)
    if scale == 0:
        return None, None
    return (max(0, qa + qb - 1) - qa * qb) / scale, (min(qa, qb) - qa * qb) / scale


def joint_failure_probability(ra, rb, rho):
    qa, qb = 1 - ra, 1 - rb
    lo, hi = frechet_bounds(ra, rb)
    if lo is None:
        if rho not in (0, None):
            raise ValueError("Pearson rho undefined for deterministic node")
        return qa * qb
    if rho < lo - 1e-12 or rho > hi + 1e-12:
        raise ValueError(f"rho={rho} outside Frechet [{lo},{hi}]")
    return qa * qb + rho * sqrt(ra * qa * rb * qb)


def parallel_reliability(ra, rb, rho=0):
    return 1 - joint_failure_probability(ra, rb, rho)


def tco_annual(capex, amortization, audit, procurement):
    if min(capex, amortization, audit, procurement) < 0:
        raise ValueError("Costs must be nonnegative")
    return capex * amortization + audit + procurement


def annual_loss(p_fail, c_day, c_scrap, duration_days):
    if not 0 <= p_fail <= 1 or min(c_day, c_scrap, duration_days) < 0:
        raise ValueError("Invalid loss inputs")
    return p_fail * (c_day * duration_days + c_scrap)


def lognormal_median(mu):
    return exp(mu)


def lognormal_mean(mu, sigma):
    if sigma < 0:
        raise ValueError("sigma < 0")
    return exp(mu + sigma * sigma / 2)


def var(losses, alpha):
    values = np.asarray(losses, dtype=float)
    if not 0 < alpha < 1 or not len(values) or np.any(~np.isfinite(values)):
        raise ValueError("Invalid loss sample or alpha")
    return float(np.quantile(values, alpha, method="inverted_cdf"))


def cvar(losses, alpha):
    """Mean of the worst 1-alpha mass; handles ties at the VaR atom."""
    values = np.asarray(losses, dtype=float)
    if not 0 < alpha < 1 or not len(values) or np.any(~np.isfinite(values)):
        raise ValueError("Invalid loss sample or alpha")
    ordered = np.sort(values)[::-1]
    tail_n = (1 - alpha) * len(values)
    full = int(np.floor(tail_n + 1e-12))
    remainder = tail_n - full
    numerator = ordered[:full].sum()
    if remainder > 1e-12:
        numerator += remainder * ordered[full]
    return float(numerator / tail_n)
