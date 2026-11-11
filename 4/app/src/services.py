import hashlib
from statistics import median
from .models import DPPPassport
from .calculators.sensitivity import SensitivityCalculator
from .calculators.cflp import lp_gap
from .calculators.sourcing_audit import SourcingAudit

class TCOService:
    def __init__(self,simulator): self.simulator=simulator
    def calculate(self):
        baseline={name:self.simulator.calculate(name) for name in self.simulator.routes}
        return dict(baseline=baseline,sensitivity=SensitivityCalculator(self.simulator).calculate(),
                    ranking=sorted(baseline,key=lambda k:baseline[k].tco_log_usd))

class CFLPService:
    def __init__(self,calculator): self.calculator=calculator
    def calculate(self,data,repeats=3):
        solutions={}; times={}
        for name,kwargs in [('multi',{}),('single',{'single':True}),('physical_lp',{'relax':True}),('bigm_milp',{'big_m':True}),('bigm_lp',{'big_m':True,'relax':True})]:
            runs=[self.calculator.solve(data,**kwargs) for _ in range(repeats)]
            if any(x.status!='Optimal' for x in runs): raise ArithmeticError(f'{name}: CBC не доказал оптимум')
            solutions[name]=runs[0]
            times[name]=dict(samples_seconds=[x.solve_seconds for x in runs],median_seconds=median(x.solve_seconds for x in runs))
        audit=SourcingAudit(self.calculator).calculate(data,solutions)
        return dict(solutions=solutions,timings=times,sourcing_audit=audit,physical_gap_pct=lp_gap(solutions['multi'].objective_rub_year,solutions['physical_lp'].objective_rub_year),
                    bigm_gap_pct=lp_gap(solutions['bigm_milp'].objective_rub_year,solutions['bigm_lp'].objective_rub_year))

class TelemetryService:
    def __init__(self,calculator,simulator): self.calculator=calculator; self.simulator=simulator
    def calculate(self,data):
        result=self.calculator.calculate(data.telemetry)
        before=self.simulator.calculate('Rail_Express')
        if result['scrap']: self.simulator.set_failure_probability('Rail_Express',1.0)
        after=self.simulator.calculate('Rail_Express')
        rail=[l for l in data.routes['Rail_Express'].legs if l.name=='Rail Mainline']
        if len(rail)!=1: raise ValueError('Не найдено однозначное ж/д плечо для Scope 3')
        result.update(before=before,after=after,delta_usd=after.tco_log_usd-before.tco_log_usd,
                      scope3_transport_emissions_tco2=result['distance_km']*rail[0].emission_g_tkm*1e-6*data.cargo.volume_tons,
                      rail_emission_factor_g_tkm=rail[0].emission_g_tkm)
        return result

class PassportService:
    def create(self,data,result):
        return DPPPassport('RAIL-EXP-2026-HF10N-04',data.cargo.material_name,'Rail_Express',
                  hashlib.sha256(data.telemetry.source.read_bytes()).hexdigest(),
                  'VIOLATED' if result['temperature_incidents'] else 'PASSED',
                  'SHOCK_DETECTED' if result['shock_incidents'] else 'NORMAL',
                  'SCRAP_WRITE_OFF' if result['scrap'] else 'RELEASE',round(result['after'].tco_log_usd,2),
                  round(result['scope3_transport_emissions_tco2'],4))
