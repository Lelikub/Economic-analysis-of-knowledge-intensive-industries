"""Годовые сценарии работоспособности и ущерба."""

import numpy as np
from scipy.optimize import brentq
from scipy.stats import multivariate_normal, norm

from .analytics import cvar, var, joint_failure_probability


def simulate_independent(reliabilities, n, seed, mu, sigma, c_day, c_scrap,
                         backup=None, duration="lognormal", pareto_alpha=None,
                         pareto_xm=None, fixed=False):
    rng = np.random.default_rng(seed)
    r = np.asarray(reliabilities, dtype=float)
    states = rng.random((n, len(r))) < r
    if backup is not None:
        backup_states = rng.random(n) < backup
        ok = states[:, 0] & (states[:, 1] | backup_states) & states[:, 2:].all(axis=1)
        states = np.column_stack([states[:, :2], backup_states, states[:, 2:]])
    else:
        ok = states.all(axis=1)
    downtime = _durations(rng, n, mu, sigma, duration, pareto_alpha, pareto_xm, fixed)
    downtime[ok] = 0
    loss = np.where(ok, 0, c_day * downtime + c_scrap)
    return {"ok": ok, "downtime": downtime, "loss": loss, "states": states}


def simulate_pair(reliabilities, backup_r, rho, n, seed, mu, sigma, c_day, c_scrap):
    """Sample exact two-node Bernoulli joint distribution; other stages independent."""
    rng = np.random.default_rng(seed)
    r = np.asarray(reliabilities, dtype=float)
    p00 = joint_failure_probability(r[1], backup_r, rho)
    p01 = 1-r[1]-p00
    p10 = 1-backup_r-p00
    draw = rng.choice(4, size=n, p=[p00, p01, p10, 1-p00-p01-p10])
    main_ok = (draw == 2) | (draw == 3)
    backup_ok = (draw == 1) | (draw == 3)
    others = rng.random((n, 4)) < r[[0, 2, 3, 4]]
    states = np.column_stack([others[:, 0], main_ok, backup_ok, others[:, 1:]])
    ok = others.all(axis=1) & (main_ok | backup_ok)
    downtime = _durations(rng, n, mu, sigma, "lognormal", None, None, False)
    downtime[ok] = 0
    loss = np.where(ok, 0, c_day*downtime+c_scrap)
    return {"ok": ok, "downtime": downtime, "loss": loss, "states": states}


def _durations(rng, n, mu, sigma, duration, alpha, xm, fixed):
    if fixed:
        return np.full(n, np.exp(mu))
    if duration == "lognormal":
        return rng.lognormal(mu, sigma, n)
    if duration == "pareto":
        if alpha is None or xm is None or alpha <= 0 or xm <= 0:
            raise ValueError("Invalid Pareto parameters")
        return xm * (1 + rng.pareto(alpha, n))
    raise ValueError(duration)


def calibrate_latent(target, reliabilities):
    """Find latent normal correlations matching binary-success Pearson pairs."""
    target = np.asarray(target, dtype=float)
    r = np.asarray(reliabilities, dtype=float)
    z = norm.ppf(r)
    latent = np.eye(len(r))
    residuals = []
    for i in range(len(r)):
        for j in range(i + 1, len(r)):
            rho = target[i, j]
            if abs(rho) < 1e-14:
                continue
            desired = r[i] * r[j] + rho * np.sqrt(r[i] * (1-r[i]) * r[j] * (1-r[j]))
            def f(lat):
                return multivariate_normal.cdf([z[i], z[j]], mean=[0, 0], cov=[[1, lat], [lat, 1]]) - desired
            if f(-.999999) * f(.999999) > 0:
                raise ValueError(f"Cannot calibrate pair {i},{j}")
            latent[i, j] = latent[j, i] = brentq(f, -.999999, .999999, xtol=1e-9)
            residuals.append(abs(f(latent[i, j])))
    eig = np.linalg.eigvalsh(latent)
    if eig.min() < -1e-8:
        raise ValueError(f"Calibrated latent matrix not PSD: min eigenvalue={eig.min()}")
    return latent, {"min_eigenvalue": float(eig.min()), "max_joint_residual": max(residuals, default=0)}


def simulate_copula(reliabilities, target, n, seed, mu, sigma, c_day, c_scrap,
                    dual, duration="lognormal", pareto_alpha=None, pareto_xm=None):
    r = np.asarray(reliabilities, dtype=float)
    latent, diagnostics = calibrate_latent(target, r)
    rng = np.random.default_rng(seed)
    z = rng.multivariate_normal(np.zeros(len(r)), latent, size=n, check_valid="raise")
    states = norm.cdf(z) < r
    if dual:
        ok = states[:, 0] & (states[:, 1] | states[:, 2]) & states[:, 3:].all(axis=1)
    else:
        ok = states[:, 0] & states[:, 1] & states[:, 3:].all(axis=1)
    downtime = _durations(rng, n, mu, sigma, duration, pareto_alpha, pareto_xm, False)
    downtime[ok] = 0
    loss = np.where(ok, 0, c_day * downtime + c_scrap)
    return {"ok": ok, "states": states, "downtime": downtime, "loss": loss,
            "latent": latent, "diagnostics": diagnostics}


def summarize_simulation(result, levels=(.95, .99)):
    loss = result["loss"]
    p_ok = float(np.mean(result["ok"]))
    out = {"r_sys_mc": p_ok, "p_fail_mc": 1-p_ok,
           "el_mc": float(np.mean(loss)),
           "r_se": float(np.sqrt(p_ok * (1-p_ok) / len(loss))),
           "el_se": float(np.std(loss, ddof=1) / np.sqrt(len(loss)))}
    for a in levels:
        suffix = str(round(a * 100))
        out[f"var{suffix}"] = var(loss, a)
        out[f"cvar{suffix}"] = cvar(loss, a)
    return out
