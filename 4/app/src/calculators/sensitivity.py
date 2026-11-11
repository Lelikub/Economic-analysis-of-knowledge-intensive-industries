from itertools import combinations
import numpy as np
import pandas as pd

def linear_root(function,low,high):
    f0=float(function(low)); f1=float(function(high)); slope=(f1-f0)/(high-low)
    if abs(slope)<1e-12:
        return dict(status='IDENTICAL_IN_RANGE' if abs(f0)<1e-8 else 'NO_CROSSING_IN_RANGE',value=None,extrapolated_value=None,residual_usd=None)
    root=low-f0/slope
    inside=low<=root<=high
    delta=max(1e-4,abs(root)*1e-7)
    signs=(function(max(low,root-delta)),function(min(high,root+delta))) if inside else (None,None)
    return dict(status='CROSSING' if inside else 'NO_CROSSING_IN_RANGE',value=root if inside else None,
                extrapolated_value=root,residual_usd=float(function(root)) if inside else None,
                sign_left=None if signs[0] is None else float(signs[0]),sign_right=None if signs[1] is None else float(signs[1]))

class SensitivityCalculator:
    def __init__(self,simulator): self.sim=simulator

    def calculate(self):
        s=self.sim; names=list(s.routes)
        output={}
        for key,grid,arg in [('wacc',np.linspace(.05,.30,51),'wacc'),('cargo_value',np.linspace(20000,500000,97),'price'),('lead_time',np.linspace(10,120,111),'total_days')]:
            rows=[]
            for v in grid:
                row={key:float(v)}
                for name in names:
                    kwargs={arg:float(v)} if key!='lead_time' or name=='Sea_Road_Multimodal' else {}
                    row[name]=s.calculate(name,**kwargs).tco_log_usd
                rows.append(row)
            output[key]=pd.DataFrame(rows)
        roots=[]
        for a,b in combinations(names,2):
            for w in [.15,.20,.25,.30]:
                f=lambda p:s.calculate(a,price=p,wacc=w).tco_log_usd-s.calculate(b,price=p,wacc=w).tco_log_usd
                roots.append(dict(parameter='price_usd_per_t',a=a,b=b,wacc=w,low=20000,high=500000,**linear_root(f,20000,500000)))
        for b in ['Air_Express','Rail_Express']:
            f=lambda t:s.calculate('Sea_Road_Multimodal',total_days=t).tco_log_usd-s.calculate(b).tco_log_usd
            roots.append(dict(parameter='sea_total_days',a='Sea_Road_Multimodal',b=b,wacc=s.cargo.wacc_baseline,low=10,high=120,**linear_root(f,10,120)))
        output['roots']=roots
        air=s.calculate('Air_Express'); rail=s.calculate('Rail_Express'); sea=s.calculate('Sea_Road_Multimodal')
        freight_delta=air.freight_usd-rail.freight_usd
        dt=rail.lead_time_days-air.lead_time_days
        rows=[]; thresholds=[]
        for p in [150000,225000,300000]:
            saving=s.cargo.volume_tons*p*s.cargo.wacc_baseline*dt/365
            carbon_slope=(air.transport_emissions_tco2_per_t-rail.transport_emissions_tco2_per_t)*s.cargo.volume_tons*s.cbam.eur_usd_rate
            threshold=s.cbam.p_carbon_origin_eur+(saving-freight_delta)/carbon_slope
            thresholds.append(dict(price_usd_per_t=p,freight_delta_usd=freight_delta,capital_saving_usd=saving,
                                   cbam_delta_baseline_usd=air.border_usd-rail.border_usd,ets_equality_eur=threshold,
                                   status='NONNEGATIVE_THRESHOLD' if threshold>=0 else 'NO_NONNEGATIVE_ETS_THRESHOLD',
                                   air_minus_rail_baseline_usd=s.calculate('Air_Express',price=p).tco_log_usd-s.calculate('Rail_Express',price=p).tco_log_usd))
            for ets in np.linspace(0,500,101):
                rows.append(dict(ets_eur_tco2=float(ets),price_usd_per_t=p,air_minus_rail_usd=s.calculate('Air_Express',price=p,ets=float(ets)).tco_log_usd-s.calculate('Rail_Express',price=p,ets=float(ets)).tco_log_usd))
        output['ets']=pd.DataFrame(rows); output['ets_thresholds']=thresholds
        output['answers']=dict(air_rail_freight_gap_usd=freight_delta,
             air_rail_freight_cbam_gap_usd=freight_delta+air.border_usd-rail.border_usd,
             air_sea_freight_cbam_gap_usd=air.freight_usd-sea.freight_usd+air.border_usd-sea.border_usd,
             price_air_rail_freight_only_usd_per_t=freight_delta*365/(s.cargo.volume_tons*s.cargo.wacc_baseline*dt),
             price_air_rail_including_cbam_usd_per_t=(freight_delta+air.border_usd-rail.border_usd)*365/(s.cargo.volume_tons*s.cargo.wacc_baseline*dt))
        output['answers']['control1_thresholds']=[dict(wacc=w,
             air_vs_rail_price_usd_per_t=next(r['extrapolated_value'] for r in roots if r['parameter']=='price_usd_per_t' and r['a']=='Air_Express' and r['b']=='Rail_Express' and r['wacc']==w),
             air_vs_sea_price_usd_per_t=next(r['extrapolated_value'] for r in roots if r['parameter']=='price_usd_per_t' and r['a']=='Air_Express' and r['b']=='Sea_Road_Multimodal' and r['wacc']==w)) for w in [.20,.25,.30]]
        for row in output['answers']['control1_thresholds']:
            row['air_globally_cheaper_above_usd_per_t']=max(row['air_vs_rail_price_usd_per_t'],row['air_vs_sea_price_usd_per_t'])
        output['answers']['control1_examples']=[dict(wacc=w,price_usd_per_t=p,
             air_log_usd=s.calculate('Air_Express',wacc=w,price=p).tco_log_usd,
             rail_log_usd=s.calculate('Rail_Express',wacc=w,price=p).tco_log_usd,
             sea_log_usd=s.calculate('Sea_Road_Multimodal',wacc=w,price=p).tco_log_usd,
             cheapest_route=min(names,key=lambda name:s.calculate(name,wacc=w,price=p).tco_log_usd)) for w,p in [(.25,22000),(.25,1500000),(.30,1200000)]]
        return output
