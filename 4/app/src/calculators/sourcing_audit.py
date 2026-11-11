"""Независимый контроль совпадения двух постановок и диагностический контрпример."""
from dataclasses import replace
from itertools import combinations
from math import isclose
from .cflp import enumerate_multi,enumerate_single

class SourcingAudit:
    def __init__(self,calculator):self.calculator=calculator

    @staticmethod
    def source_counts(data,solution):
        return {c.customer_id:sum(solution.flows[f.facility_id][c.customer_id]>1e-6 for f in data.facilities) for c in data.customers}

    def calculate(self,data,solutions):
        multi=solutions['multi'];single=solutions['single']
        delta=max(abs(multi.flows[f.facility_id][c.customer_id]-single.flows[f.facility_id][c.customer_id]) for f in data.facilities for c in data.customers)
        opened=[f for f in data.facilities if multi.y[f.facility_id]>.5]
        rows=[];demand=sum(c.demand_tons_year for c in data.customers)
        # Нижняя граница для каждого набора открытий: каждому клиенту выбирается
        # самый дешёвый тариф без ограничений мощностей. Это не может завысить оптимум.
        for n in range(1,len(data.facilities)+1):
            for subset in combinations(data.facilities,n):
                capacity=sum(f.capacity_tons_year for f in subset)
                if capacity<demand:continue
                fixed=sum(f.fixed_cost_rub_year for f in subset)
                transport=sum(c.demand_tons_year*min(data.tariffs.values[f.facility_id,c.customer_id] for f in subset) for c in data.customers)
                rows.append(dict(open_hubs=[f.facility_id for f in subset],capacity_tons_year=capacity,
                                 fixed_rub_year=fixed,unconstrained_transport_lower_bound_rub_year=transport,total_lower_bound_rub_year=fixed+transport))
        multi_independent=enumerate_multi(data)
        single_independent=enumerate_single(data)['objective_rub_year']
        baseline=dict(multi_rub_year=multi.objective_rub_year,single_rub_year=single.objective_rub_year,
                      independent_multi_rub_year=multi_independent,independent_single_rub_year=single_independent,
                      max_flow_difference_tons_year=delta,identical_flows=delta<1e-6,
                      multi_source_counts=self.source_counts(data,multi),single_source_counts=self.source_counts(data,single),
                      open_hub_ids=[f.facility_id for f in opened],lower_bounds_by_open_set=rows,
                      minimum_lower_bound_rub_year=min(r['total_lower_bound_rub_year'] for r in rows),
                      sum_two_largest_capacities_tons_year=sum(sorted((f.capacity_tons_year for f in data.facilities),reverse=True)[:2]))
        # Только диагностический сценарий в памяти; исходный CSV и baseline неизменны.
        variant=replace(data,facilities=tuple(replace(f,capacity_tons_year=650) if f.facility_id=='B' else f for f in data.facilities))
        vm=self.calculator.solve(variant);vs=self.calculator.solve(variant,single=True)
        independent_vm=enumerate_multi(variant);independent_vs=enumerate_single(variant)['objective_rub_year']
        diagnostic=dict(description='Только контроль: мощность B — Тверь снижена с 700 до 650 тонн/год; первичные файлы не менялись',
                        facility_id='B',capacity_tons_year=650,baseline_unchanged=True,
                        multi_status=vm.status,single_status=vs.status,
                        multi_rub_year=vm.objective_rub_year,single_rub_year=vs.objective_rub_year,
                        independent_multi_rub_year=independent_vm,independent_single_rub_year=independent_vs,
                        multi_flows=vm.flows,single_flows=vs.flows,
                        multi_source_counts=self.source_counts(variant,vm),single_source_counts=self.source_counts(variant,vs),
                        extra_cost_single_rub_year=vs.objective_rub_year-vm.objective_rub_year)
        checks=[isclose(multi.objective_rub_year,multi_independent,abs_tol=.01),
                isclose(single.objective_rub_year,single_independent,abs_tol=.01),
                isclose(multi.objective_rub_year,baseline['minimum_lower_bound_rub_year'],abs_tol=.01),
                isclose(vm.objective_rub_year,independent_vm,abs_tol=.01),
                isclose(vs.objective_rub_year,independent_vs,abs_tol=.01),
                baseline['identical_flows'],all(v==1 for v in baseline['multi_source_counts'].values()),
                any(v>1 for v in diagnostic['multi_source_counts'].values()),
                all(v==1 for v in diagnostic['single_source_counts'].values()),diagnostic['extra_cost_single_rub_year']>0]
        if not all(checks):raise ArithmeticError('Проверка различия постановок снабжения не пройдена')
        return dict(status='PASS',baseline=baseline,diagnostic=diagnostic,
                    interpretation='В базовом оптимуме дробление разрешено, но не требуется; совпадение графиков корректно. Диагностический сценарий подтверждает различие моделей.')
