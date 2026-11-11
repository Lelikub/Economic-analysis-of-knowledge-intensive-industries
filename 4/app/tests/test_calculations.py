from dataclasses import replace
from datetime import timedelta
import hashlib
import math
import pytest
from src.calculators.tco import MultimodalTCOSimulator, CBAMCalculator
from src.calculators.sensitivity import SensitivityCalculator, linear_root
from src.calculators.cflp import CFLPCalculator, lp_gap, enumerate_single
from src.calculators.telemetry import TelemetryCalculator, haversine
from src.validators import DataValidator
from src.services import TCOService, TelemetryService, PassportService

def test_load_shapes(data):
    assert len(data.routes) == 3
    assert len(data.telemetry.samples) == 1440
    assert sum(c.demand_tons_year for c in data.cflp.customers) == 1600
    assert sum(f.capacity_tons_year for f in data.cflp.facilities) == 2750
    assert len(data.cflp.tariffs.values) == 20

@pytest.mark.parametrize('route', ['Air_Express','Rail_Express','Sea_Road_Multimodal'])
def test_tco_independent(data, route):
    c=data.cargo; r=data.routes[route]; b=data.cbam
    x=MultimodalTCOSimulator(c,b,data.routes).calculate(route)
    expected=sum(l.distance_km*l.tariff_usd_tkm*c.volume_tons for l in r.legs)
    expected+=c.volume_tons*c.price_usd_per_ton*(c.insurance_rate+c.wacc_baseline*sum(l.lead_time_days for l in r.legs)/365)
    expected+=c.pack_comp_cost_usd+c.p_fail_base*c.l_fail_loss_usd
    expected+=max(0,b.see_prod_tco2_per_ton+sum(l.distance_km*l.emission_g_tkm/1e6 for l in r.legs)-b.benchmark_eu_tco2_per_ton)*c.volume_tons*(b.p_eu_ets_eur-b.p_carbon_origin_eur)*b.eur_usd_rate
    assert x.tco_log_usd == pytest.approx(expected,abs=1e-7)
    assert x.tco_total_usd-x.tco_log_usd == pytest.approx(440000)

@pytest.mark.parametrize('p',[0,1])
def test_risk_bounds(data,p):
    s=MultimodalTCOSimulator(data.cargo,data.cbam,data.routes)
    s.set_failure_probability('Rail_Express',p)
    assert s.calculate('Rail_Express').risk_usd == p*1200000

def test_zero_wacc(data):
    s=MultimodalTCOSimulator(data.cargo,data.cbam,data.routes)
    assert s.calculate('Rail_Express',wacc=0).inventory_usd == 0

def test_cbam_below_benchmark(data):
    b=replace(data.cbam,benchmark_eu_tco2_per_ton=100)
    assert CBAMCalculator().calculate(data.cargo,b,data.routes['Air_Express'])[0] == 0

def test_negative_price_spread_preserved(data):
    b=replace(data.cbam,p_eu_ets_eur=1)
    assert CBAMCalculator().calculate(data.cargo,b,data.routes['Air_Express'])[0] < 0

@pytest.mark.parametrize('field,value',[('volume_tons',0),('price_usd_per_ton',-1),('p_fail_base',1.01),('wacc_baseline',15),('insurance_rate',float('nan'))])
def test_invalid_cargo(data,field,value):
    with pytest.raises(ValueError):
        DataValidator().validate(replace(data,cargo=replace(data.cargo,**{field:value})))

def test_invalid_tariff_ids(data):
    t=replace(data.cflp.tariffs,values={('BAD','1'):1})
    with pytest.raises(ValueError):
        DataValidator().validate(replace(data,cflp=replace(data.cflp,tariffs=t)))

def test_zero_route_distance(data):
    r=data.routes['Rail_Express']; routes=dict(data.routes)
    routes[r.route_id]=replace(r,legs=(replace(r.legs[0],distance_km=0),)+r.legs[1:])
    with pytest.raises(ValueError): DataValidator().validate(replace(data,routes=routes))

def test_linear_root():
    assert linear_root(lambda x: x-3,0,5)['value'] == pytest.approx(3)
    assert linear_root(lambda x: x-8,0,5)['status'] == 'NO_CROSSING_IN_RANGE'
    assert linear_root(lambda x: 1,0,5)['value'] is None

def test_no_evaluation_outside_root_domain(data):
    s=MultimodalTCOSimulator(data.cargo,data.cbam,data.routes)
    base=s.calculate('Sea_Road_Multimodal',total_days=10).tco_log_usd
    slope=data.cargo.volume_tons*data.cargo.price_usd_per_ton*data.cargo.wacc_baseline/365
    def difference(t):
        return s.calculate('Sea_Road_Multimodal',total_days=t).tco_log_usd-base+9*slope
    result=linear_root(difference,10,120)
    assert result['status']=='NO_CROSSING_IN_RANGE'
    assert result['extrapolated_value']==pytest.approx(1)
    assert result['residual_usd'] is None

def test_sensitivity(data):
    s=MultimodalTCOSimulator(data.cargo,data.cbam,data.routes)
    out=SensitivityCalculator(s).calculate()
    for r in data.routes:
        assert out['wacc'][r].is_monotonic_increasing
        assert out['cargo_value'][r].is_monotonic_increasing
    for root in out['roots']:
        if root['status']=='CROSSING': assert abs(root['residual_usd']) < 1e-5

@pytest.mark.parametrize('single',[False,True])
def test_cflp(data,single):
    x=CFLPCalculator().solve(data.cflp,single=single)
    assert x.status=='Optimal'
    assert max(abs(v) for v in x.demand_residuals.values())<1e-6
    assert min(x.capacity_slacks.values())>=-1e-6
    assert x.objective_rub_year==pytest.approx(x.fixed_rub_year+x.transport_rub_year)
    if single: assert x.objective_rub_year==pytest.approx(enumerate_single(data.cflp)['objective_rub_year'])

def test_multi_and_single_can_differ_when_capacity_requires_split(data):
    # Only a diagnostic in-memory scenario; primary input files stay unchanged.
    variant=replace(data.cflp,facilities=tuple(replace(f,capacity_tons_year=650) if f.facility_id=='B' else f for f in data.cflp.facilities))
    calc=CFLPCalculator()
    multi=calc.solve(variant)
    single=calc.solve(variant,single=True)
    assert multi.status==single.status=='Optimal'
    assert multi.objective_rub_year<single.objective_rub_year
    assert any(sum(multi.flows[f.facility_id][c.customer_id]>1e-6 for f in variant.facilities)>1 for c in variant.customers)
    assert all(sum(single.flows[f.facility_id][c.customer_id]>1e-6 for f in variant.facilities)==1 for c in variant.customers)
    assert single.objective_rub_year==pytest.approx(enumerate_single(variant)['objective_rub_year'])

def test_lp_bounds_and_bigm(data):
    calc=CFLPCalculator()
    for big in [False,True]:
        a=calc.solve(data.cflp,big_m=big); b=calc.solve(data.cflp,big_m=big,relax=True)
        assert a.status==b.status=='Optimal'
        assert b.objective_rub_year<=a.objective_rub_year+1e-5
        assert lp_gap(a.objective_rub_year,b.objective_rub_year)>=0
    assert max(calc.solve(data.cflp,big_m=True).physical_overloads.values())>0

def test_infeasible(data):
    d=replace(data.cflp,facilities=tuple(replace(f,capacity_tons_year=1) for f in data.cflp.facilities))
    r=CFLPCalculator().solve(d)
    assert r.status=='Infeasible'
    assert r.objective_rub_year is None

def test_zero_gap_denominator():
    assert lp_gap(0,0)==0
    assert lp_gap(0,1) is None

def test_telemetry_regression(data):
    x=TelemetryCalculator().calculate(data.telemetry)
    assert len(x['temperature_incidents'])==1
    e=x['temperature_incidents'][0]
    assert (e.start_index,e.end_index,e.duration_minutes)==(540,548,45)
    assert x['shock_incidents'][0].start_index==920
    assert x['peak_axis_g']==pytest.approx(2.65)
    assert x['peak_norm_g']==pytest.approx(math.sqrt(1.15**2+.95**2+2.65**2))

@pytest.mark.parametrize('n,expected',[(6,False),(7,True)])
def test_duration_boundary(data,n,expected):
    samples=tuple(replace(s,temp_celsius=-17) for s in data.telemetry.samples[:n])
    x=TelemetryCalculator().calculate(replace(data.telemetry,samples=samples))
    assert x['scrap'] is expected

@pytest.mark.parametrize('temp',[-22,-18])
def test_temperature_inclusive(data,temp):
    d=replace(data.telemetry,samples=(replace(data.telemetry.samples[0],temp_celsius=temp),))
    assert not TelemetryCalculator().calculate(d)['temperature_incidents']

def test_missing_sample_breaks_episode(data):
    samples=tuple(replace(s,temp_celsius=-17) for s in data.telemetry.samples[:9] if s.index!=4)
    x=TelemetryCalculator().calculate(replace(data.telemetry,samples=samples))
    assert len(x['temperature_incidents'])==2
    assert not x['scrap']

@pytest.mark.parametrize('axis,shock',[(2.5,False),(2.5001,True),(-2.6,True)])
def test_shock_threshold(data,axis,shock):
    d=replace(data.telemetry,samples=(replace(data.telemetry.samples[0],accel_x_g=axis,accel_y_g=0,accel_z_g=0),))
    assert bool(TelemetryCalculator().calculate(d)['shock_incidents']) is shock

def test_haversine():
    assert haversine(0,0,0,1)==pytest.approx(111.19508,rel=1e-6)
    assert haversine(52,13,52,13)==0

def test_coordinate_error(data):
    d=replace(data.telemetry,samples=(replace(data.telemetry.samples[0],latitude=91),)+data.telemetry.samples[1:])
    with pytest.raises(ValueError): DataValidator().validate(replace(data,telemetry=d))

def test_integration_trigger(data):
    sim=MultimodalTCOSimulator(data.cargo,data.cbam,data.routes)
    base=TCOService(sim).calculate()
    before=sim.calculate('Air_Express')
    x=TelemetryService(TelemetryCalculator(),sim).calculate(data)
    assert sim.routes['Rail_Express'] is data.routes['Rail_Express']
    assert x['after'].tco_log_usd-x['before'].tco_log_usd==pytest.approx(1194000)
    assert sim.calculate('Air_Express')==before
    p=PassportService().create(data,x)
    assert p.adjusted_tco_usd==round(x['after'].tco_log_usd,2)
    assert p.sha256_telemetry_digest==hashlib.sha256(data.telemetry.source.read_bytes()).hexdigest()
    assert p.final_disposition=='SCRAP_WRITE_OFF'
