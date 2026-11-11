from math import isfinite
from ..models import TCOBreakdown

class CBAMCalculator:
    def calculate(self,cargo,cbam,route,ets=None):
        e=sum(l.distance_km*l.emission_g_tkm*1e-6 for l in route.legs)
        tax=max(0,cbam.see_prod_tco2_per_ton+e-cbam.benchmark_eu_tco2_per_ton)*cargo.volume_tons*((cbam.p_eu_ets_eur if ets is None else ets)-cbam.p_carbon_origin_eur)
        return tax,tax*cbam.eur_usd_rate,e

class MultimodalTCOSimulator:
    """Единый движок. Меняется только вероятность конкретного сценария, не исходный CargoProfile."""
    def __init__(self,cargo,cbam,routes):
        self.cargo=cargo; self.cbam=cbam; self.routes=routes
        self.probabilities={name:cargo.p_fail_base for name in routes}
        self.cbam_calculator=CBAMCalculator()

    def set_failure_probability(self,route_id,value):
        if not isinstance(value,(int,float)) or not isfinite(value) or not 0<=value<=1: raise ValueError('p_fail вне [0,1]')
        if route_id not in self.routes: raise KeyError(route_id)
        self.probabilities[route_id]=value

    def calculate(self,route_id,*,price=None,wacc=None,total_days=None,ets=None):
        c=self.cargo; r=self.routes[route_id]
        p=c.price_usd_per_ton if price is None else price
        w=c.wacc_baseline if wacc is None else wacc
        t=sum(l.lead_time_days for l in r.legs) if total_days is None else total_days
        for value,name in [(p,'price'),(w,'wacc'),(t,'days')]:
            if not isinstance(value,(int,float)) or not isfinite(value) or value<0: raise ValueError(name)
        if p==0 or w>1: raise ValueError('price >0, WACC <=1')
        if ets is not None and (not isfinite(ets) or ets<0): raise ValueError('ETS>=0')
        if total_days is not None:
            if route_id!='Sea_Road_Multimodal': raise ValueError('Время изменяется только у морского сценария')
            fixed=sum(l.lead_time_days for l in r.legs if l.name!='Deep-Sea Maritime')
            if t<fixed: raise ValueError('Отрицательное время морского плеча')
        freight=sum(l.distance_km*l.tariff_usd_tkm*c.volume_tons for l in r.legs)
        insurance=c.volume_tons*p*c.insurance_rate
        inventory=c.volume_tons*p*w/365*t
        risk=self.probabilities[route_id]*c.l_fail_loss_usd
        tax,border,e=self.cbam_calculator.calculate(c,self.cbam,r,ets)
        log=freight+insurance+inventory+c.pack_comp_cost_usd+risk+border
        return TCOBreakdown(route_id,freight,insurance,inventory,c.pack_comp_cost_usd,risk,tax,border,e,t,self.probabilities[route_id],log,log+c.volume_tons*p)
