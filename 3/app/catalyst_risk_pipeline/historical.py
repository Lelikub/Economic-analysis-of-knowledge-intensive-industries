"""Анализ эмпирических инцидентов без изменения зарегистрированных потерь."""

import numpy as np
from scipy.optimize import minimize
from scipy import stats


class HistoricalIncidentAnalyzer:
    def analyze(self, incidents, c_day, c_scrap, seed=202603):
        durations = np.array([x.downtime_days for x in incidents], dtype=float)
        observed = np.array([x.direct_loss for x in incidents], dtype=float)
        expected = c_day * durations + c_scrap
        residuals = observed - expected
        log_t = np.log(durations)
        mu_hat = float(log_t.mean())
        sigma_hat = float(log_t.std(ddof=0))
        shapiro = stats.shapiro(log_t)
        # Fixed-prior KS is valid because these parameters came from JSON, not this sample.
        prior_ks = stats.kstest(durations, "lognorm", args=(self.prior_sigma, 0, np.exp(self.prior_mu))) if hasattr(self, "prior_mu") else None
        fitted_stat = stats.kstest(durations, "lognorm", args=(sigma_hat, 0, np.exp(mu_hat))).statistic
        rng = np.random.default_rng(seed)
        boot = []
        for _ in range(500):
            sample = rng.lognormal(mu_hat, sigma_hat, len(durations))
            m = np.log(sample).mean()
            s = np.log(sample).std(ddof=0)
            boot.append(stats.kstest(sample, "lognorm", args=(s, 0, np.exp(m))).statistic)
        boot_p = (1 + np.sum(np.asarray(boot) >= fitted_stat)) / (1 + len(boot))
        xm = getattr(self, "pareto_xm", 2.0)
        alpha_prior = getattr(self, "pareto_alpha", 1.3)
        tail = durations[durations >= xm]
        pareto_stats = {"tail_count": int(len(tail)), "threshold_days": float(xm),
                        "prior_alpha": float(alpha_prior)}
        if len(tail) >= 10:
            alpha_hat = len(tail) / np.log(tail/xm).sum()
            pareto_ks = stats.kstest(tail, "pareto", args=(alpha_hat, 0, xm)).statistic
            boot_pareto = []
            for _ in range(500):
                sample = xm * (1+rng.pareto(alpha_hat, len(tail)))
                ah = len(sample)/np.log(sample/xm).sum()
                boot_pareto.append(stats.kstest(sample, "pareto", args=(ah, 0, xm)).statistic)
            def neg_ll(params):
                m, log_s = params
                s = np.exp(log_s)
                return -float(np.sum(stats.lognorm.logpdf(tail, s, scale=np.exp(m)))
                              - len(tail)*np.log(stats.lognorm.sf(xm, s, scale=np.exp(m))))
            fit = minimize(neg_ll, [mu_hat, np.log(sigma_hat)], method="Nelder-Mead")
            ll_ln = -float(fit.fun)
            ll_par = float(np.sum(stats.pareto.logpdf(tail, alpha_hat, scale=xm)))
            pareto_stats.update({"fitted_alpha": float(alpha_hat),
                "ks_fitted_stat": float(pareto_ks),
                "ks_bootstrap_p": float((1+np.sum(np.asarray(boot_pareto)>=pareto_ks))/(1+len(boot_pareto))),
                "aic_pareto": float(2-2*ll_par), "bic_pareto": float(np.log(len(tail))-2*ll_par),
                "aic_truncated_lognormal": float(4-2*ll_ln),
                "bic_truncated_lognormal": float(2*np.log(len(tail))-2*ll_ln),
                "prior_ks_p": float(stats.kstest(tail, "pareto", args=(alpha_prior,0,xm)).pvalue),
                "truncated_lognormal_fit_success": bool(fit.success)})
        q1, q3 = np.quantile(durations, [.25, .75])
        upper = q3 + 1.5 * (q3 - q1)
        return {
            "count": len(durations), "downtime_mean": float(durations.mean()),
            "downtime_median": float(np.median(durations)), "downtime_q1": float(q1),
            "downtime_q3": float(q3), "downtime_std": float(durations.std(ddof=1)),
            "downtime_min": float(durations.min()), "downtime_max": float(durations.max()),
            "outlier_count": int(np.sum(durations > upper)), "outlier_upper": float(upper),
            "loss_mean": float(observed.mean()), "loss_median": float(np.median(observed)),
            "loss_std": float(observed.std(ddof=1)), "loss_min": float(observed.min()),
            "loss_max": float(observed.max()),
            "mu_fitted": mu_hat, "sigma_fitted": sigma_hat,
            "shapiro_stat": float(shapiro.statistic), "shapiro_p": float(shapiro.pvalue),
            "ks_fitted_stat": float(fitted_stat), "ks_bootstrap_p": float(boot_p),
            "ks_prior_stat": float(prior_ks.statistic) if prior_ks else None,
            "ks_prior_p": float(prior_ks.pvalue) if prior_ks else None,
            "residual_mean": float(residuals.mean()), "residual_max_abs": float(np.max(np.abs(residuals))),
            "residual_nonzero": int(np.sum(np.abs(residuals) > 1e-6)),
            "pareto": pareto_stats,
            "residual_rows": [{"id": x.incident_id, "observed": float(o),
                               "model": float(e), "residual": float(r)}
                              for x, o, e, r in zip(incidents, observed, expected, residuals)],
        }

    def set_prior(self, mu, sigma, pareto_alpha=1.3, pareto_xm=2.0):
        self.prior_mu, self.prior_sigma = mu, sigma
        self.pareto_alpha, self.pareto_xm = pareto_alpha, pareto_xm
        return self
