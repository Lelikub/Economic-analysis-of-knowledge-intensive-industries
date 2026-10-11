"""Проверки исходных величин и математической допустимости."""

import math

import numpy as np

from .analytics import frechet_bounds, tco_annual
from .loaders import canonical


class DataValidator:
    def validate(self, data):
        issues = []
        def add(kind, field, description, severity="WARNING", status="UNRESOLVED"):
            issues.append({"type": kind, "field": field, "description": description,
                           "severity": severity, "status": status})
        cfg = data.raw_json
        for key, node in data.nodes.items():
            if not all(math.isfinite(v) for v in (node.reliability, node.unreliability, node.availability, node.mtbf_hours, node.mttr_hours)):
                add("DATA_INVALID", key, "Nonfinite node value", "BLOCKER")
            if not all(0 <= v <= 1 for v in (node.reliability, node.unreliability, node.availability)):
                add("DATA_INVALID", key, "R/Q/A outside [0,1]", "BLOCKER")
            if abs(node.unreliability - (1-node.reliability)) > 1e-4:
                add("DATA_CONFLICT", key, "Q differs from 1-R", "BLOCKER")
            if node.mtbf_hours <= 0 or node.mttr_hours <= 0 or node.lead_time_days < 0:
                add("DATA_INVALID", key, "Invalid time parameter", "BLOCKER")
            calc_a = node.mtbf_hours / (node.mtbf_hours + node.mttr_hours)
            if abs(calc_a - node.availability) > 1e-4:
                add("DATA_CONFLICT", key, f"A={node.availability}; MTBF/(MTBF+MTTR)={calc_a:.6f}")
            if key not in cfg["nodes"]:
                add("DATA_CONFLICT", key, "Node missing in master JSON", "BLOCKER")
            elif abs(node.reliability - float(cfg["nodes"][key]["R_i"])) > 1e-8:
                add("DATA_CONFLICT", key, f"CSV R={node.reliability}; JSON R={cfg['nodes'][key]['R_i']}", "BLOCKER")
        if len(data.nodes) != 6:
            add("DATA_INVALID", "nodes", "Expected 6 source nodes", "BLOCKER")
        f, d, t = data.financial, data.downtime, data.redundancy
        checks = [("c_day", f.c_day, cfg["financial_parameters"]["c_day"]),
                  ("c_scrap", f.c_scrap, cfg["financial_parameters"]["c_scrap"]),
                  ("lognorm_mu", d.lognorm_mu, cfg["downtime_parameters"]["lognorm_mu"]),
                  ("lognorm_sigma", d.lognorm_sigma, cfg["downtime_parameters"]["lognorm_sigma"]),
                  ("pareto_alpha", d.pareto_alpha, cfg["downtime_parameters"]["pareto_alpha"]),
                  ("pareto_xm_days", d.pareto_xm_days, cfg["downtime_parameters"]["pareto_xm_days"])]
        for field, csv_value, json_value in checks:
            if not math.isfinite(csv_value) or abs(csv_value - json_value) > 1e-8:
                add("DATA_CONFLICT", field, f"CSV={csv_value}; JSON={json_value}", "BLOCKER")
        for field in (f.c_day, f.c_scrap, f.annual_budget, t.capex_qual, t.r_amor,
                      t.opex_audit, t.delta_c_proc):
            if field < 0 or not math.isfinite(field):
                add("DATA_INVALID", "financial", "Negative/nonfinite cost", "BLOCKER")
        if f.c_day == 0 or d.lognorm_sigma < 0 or d.pareto_alpha <= 0 or d.pareto_xm_days <= 0:
            add("DATA_INVALID", "distributions", "Invalid duration/cost model", "BLOCKER")
        computed_tco = tco_annual(t.capex_qual, t.r_amor, t.opex_audit, t.delta_c_proc)
        if abs(computed_tco - t.stated_tco) > 1e-4 or abs(computed_tco - cfg["redundancy_tco"]["tco_annual_calculated"]) > 1e-4:
            add("DATA_CONFLICT", "TCO", f"Calculated={computed_tco}, CSV={t.stated_tco}, JSON={cfg['redundancy_tco']['tco_annual_calculated']}", "BLOCKER")
        for label, matrix, json_key, reliabilities in (
            ("base", data.base_matrix, "base_case", [data.nodes[k].reliability for k in data.base_matrix.names]),
            ("stress", data.stress_matrix, "stress_shock_case", [(.8 if k == "Node_1_PGM" else data.nodes[k].reliability) for k in data.stress_matrix.names]),
        ):
            m = matrix.values
            if m.shape != (6, 6) or not np.all(np.isfinite(m)) or not np.allclose(m, m.T, atol=1e-10) or not np.allclose(np.diag(m), 1, atol=1e-10) or np.max(np.abs(m)) > 1+1e-10:
                add("MATH_INVALID", label, "Malformed correlation matrix", "BLOCKER")
                continue
            eig = np.linalg.eigvalsh(m)
            if eig.min() < -1e-8:
                add("MATH_INVALID", label, f"Matrix not PSD: eigenvalue={eig.min()}", "BLOCKER")
            if tuple(canonical(x) for x in cfg["correlation_matrices"]["nodes_order"]) != matrix.names:
                add("DATA_CONFLICT", label, "JSON matrix node order differs", "BLOCKER")
            if not np.allclose(m, cfg["correlation_matrices"][json_key], atol=1e-10):
                add("DATA_CONFLICT", label, "CSV/JSON matrix values differ", "BLOCKER")
            for i in range(6):
                for j in range(i+1, 6):
                    lo, hi = frechet_bounds(reliabilities[i], reliabilities[j])
                    if lo is not None and not lo-1e-8 <= m[i, j] <= hi+1e-8:
                        add("MATH_INVALID", f"{label}:{matrix.names[i]}/{matrix.names[j]}",
                            f"rho={m[i,j]} outside [{lo:.5f},{hi:.5f}]", "BLOCKER")
        for row in data.frechet_rows:
            a, b = row["Pair_Node_1"], row["Pair_Node_2"]
            lo, hi = frechet_bounds(data.nodes[a].reliability, data.nodes[b].reliability)
            if abs(lo-float(row["Frechet_Rho_Min"])) > 1e-3 or abs(hi-float(row["Frechet_Rho_Max"])) > 1e-3:
                add("DATA_CONFLICT", f"Frechet:{a}/{b}", f"Calculated [{lo:.5f},{hi:.5f}] differs from rounded CSV")
        if len(data.incidents) != 50:
            add("DATA_CONFLICT", "historical_incidents", f"Expected 50, got {len(data.incidents)}")
        ids = [x.incident_id for x in data.incidents]
        if len(ids) != len(set(ids)):
            add("DATA_INVALID", "Incident_ID", "Duplicate incident IDs", "BLOCKER")
        for x in data.incidents:
            if x.failed_node not in data.nodes or x.downtime_days <= 0 or x.direct_loss < 0:
                add("DATA_INVALID", x.incident_id, "Invalid incident node, duration or loss", "BLOCKER")
        return issues
