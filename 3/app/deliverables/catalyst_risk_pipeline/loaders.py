"""Загрузка JSON/CSV, явная нормализация ID и протокол исходных файлов."""

import csv
import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np

from .models import (CorrelationMatrix, DowntimeDistributionParameters,
                     FinancialParameters, HistoricalIncident, NodeParameters,
                     RedundancyCostParameters, SupplyChainData)


ALIASES = {
    "Node_2_HF_Main": "Node_2_UltraPure_HF_Main",
    "Node_2_HF_Backup": "Node_2_UltraPure_HF_Backup",
    "Node_4_Nitrogen": "Node_4_Liquid_Nitrogen",
    "Node_5_Reactor": "Node_5_Membrane_Reactor",
}

INPUTS = (
    "variant_b_catalyst_chain_config.json", "variant_b_nodes_parameters.csv",
    "variant_b_financial_parameters.csv", "variant_b_corr_matrix_base.csv",
    "variant_b_corr_matrix_stress.csv", "variant_b_frechet_bounds.csv",
    "variant_b_redundancy_tco.csv", "variant_b_historical_incidents_log.csv",
)


def canonical(name):
    return ALIASES.get(name, name)


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        rows = list(reader)
        if not reader.fieldnames or any(None in row for row in rows):
            raise ValueError(f"Malformed CSV: {path}")
        return rows, tuple(reader.fieldnames)


class InputDataLoader:
    def load(self, source_dir):
        directory = Path(source_dir).resolve()
        records = []
        for filename in INPUTS:
            path = directory / filename
            if not path.is_file():
                raise FileNotFoundError(path)
            data = path.read_bytes()
            records.append({"file": filename, "path": str(path), "size": len(data),
                            "sha256": hashlib.sha256(data).hexdigest(),
                            "read_utc": datetime.now(timezone.utc).isoformat()})
        config = json.loads((directory / INPUTS[0]).read_text(encoding="utf-8-sig"))
        if not all(k in config for k in ("nodes", "financial_parameters", "downtime_parameters", "correlation_matrices")):
            raise ValueError("Master JSON missing required sections")
        node_rows, columns = read_csv(directory / INPUTS[1])
        records[1].update(rows=len(node_rows), columns=columns)
        nodes = {}
        for row in node_rows:
            key = row["Node_ID"]
            if key in nodes:
                raise ValueError(f"Duplicate node {key}")
            nodes[key] = NodeParameters(key, row["Node_Name_RU"], float(row["Reliability_R"]),
                float(row["Unreliability_Q"]), float(row["Operational_Availability_A"]),
                float(row["Failure_Rate_Lambda_per_year"]), float(row["MTBF_Hours"]),
                float(row["MTTR_Hours"]), float(row["Lead_Time_Days"]), row["Criticality_Level"],
                row["Supplier_Cluster"], row["Benchmark_Source"])
        fin_rows, columns = read_csv(directory / INPUTS[2])
        records[2].update(rows=len(fin_rows), columns=columns)
        f = {row["Parameter"].split(" (")[0]: float(row["Value"]) for row in fin_rows}
        finance = FinancialParameters(f["C_day"], f["C_scrap"], float(config["financial_parameters"]["annual_budget"]))
        downtime = DowntimeDistributionParameters(f["Lognormal_mu"], f["Lognormal_sigma"], f["Pareto_alpha"], f["Pareto_xm"])
        tco_rows, columns = read_csv(directory / INPUTS[6])
        records[6].update(rows=len(tco_rows), columns=columns)
        t = {row["Cost_Component"].split(" (")[0]: float(row["Value"]) for row in tco_rows}
        redundancy = RedundancyCostParameters(t["CAPEX_qual"], t["r_amor"], t["OPEX_audit"], t["Delta_C_proc"], t["TCO_red_annual"])
        base = self._matrix(directory / INPUTS[3], nodes)
        stress = self._matrix(directory / INPUTS[4], nodes)
        records[3].update(rows=6, columns=base.names)
        records[4].update(rows=6, columns=stress.names)
        frechet_rows, columns = read_csv(directory / INPUTS[5])
        records[5].update(rows=len(frechet_rows), columns=columns)
        incident_rows, columns = read_csv(directory / INPUTS[7])
        records[7].update(rows=len(incident_rows), columns=columns)
        incidents = tuple(HistoricalIncident(row["Incident_ID"], date.fromisoformat(row["Date"]),
            canonical(row["Failed_Node"]), row["Root_Cause"], float(row["Downtime_Days"]),
            float(row["Direct_Loss_USD_Millions"])) for row in incident_rows)
        records[0].update(keys=tuple(config))
        return SupplyChainData(nodes, finance, downtime, redundancy, base, stress,
                               tuple(frechet_rows), incidents, config, tuple(records))

    def _matrix(self, path, nodes):
        rows, columns = read_csv(path)
        names = tuple(canonical(x) for x in columns[1:])
        if len(names) != 6 or len(set(names)) != 6 or set(names) != set(nodes):
            raise ValueError(f"Invalid matrix column IDs: {path}")
        row_names = tuple(canonical(row[columns[0]]) for row in rows)
        if row_names != names:
            raise ValueError(f"Matrix row/column order mismatch: {path}")
        matrix = np.array([[float(row[col]) for col in columns[1:]] for row in rows])
        return CorrelationMatrix(names, matrix)
