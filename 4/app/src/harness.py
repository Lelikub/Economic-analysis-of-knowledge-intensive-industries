import csv
import hashlib
import json
from datetime import datetime,timezone
from decimal import Decimal,localcontext
from math import isclose,sin,cos,acos,radians
from pathlib import Path
import logging
from .calculators.cflp import enumerate_single,enumerate_multi

HEADERS='Run_ID,Timestamp,Stage,Module,Test_ID,Metric,Calculated,Reference,Abs_Delta,Rel_Delta_Pct,Tolerance,Unit,Status,Severity,Source,Error_Type,Error_Message,Traceback_or_Log_Path,Probable_Cause,Corrective_Action,Retest_Status,Comment'.split(',')

class VerificationHarness:
    def __init__(self,directory,run_id):
        self.directory=Path(directory); self.directory.mkdir(parents=True,exist_ok=True)
        self.run_id=run_id; self.rows=[]

    def record(self,test_id,stage,status,*,module='',metric='',calculated='',reference='',tolerance='',unit='',source='',comment='',error='',cause='',action='',retest='',log_path=''):
        delta=''; relative=''
        if isinstance(calculated,(int,float)) and isinstance(reference,(int,float)):
            delta=abs(calculated-reference); relative=delta/abs(reference)*100 if reference else (0 if delta==0 else '')
        row=dict.fromkeys(HEADERS,'')
        row.update(Run_ID=self.run_id,Timestamp=datetime.now(timezone.utc).isoformat(),Stage=stage,Module=module,Test_ID=test_id,Metric=metric,
                   Calculated=calculated,Reference=reference,Abs_Delta=delta,Rel_Delta_Pct=relative,Tolerance=tolerance,Unit=unit,Status=status,
                   Severity='ERROR' if status in ('FAIL','BLOCKED') else 'WARNING' if status in ('WARNING','NOT_VERIFIED') else 'INFO',Source=source,
                   Error_Type=error,Error_Message=comment if error else '',Traceback_or_Log_Path=log_path,Probable_Cause=cause,Corrective_Action=action,Retest_Status=retest,Comment=comment)
        self.rows.append(row)
        path=self.directory/'HARNESS_LOG.csv'; exists=path.exists()
        with path.open('a',encoding='utf-8-sig',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=HEADERS)
            if not exists: writer.writeheader()
            writer.writerow(row)
        with (self.directory/'HARNESS_LOG.md').open('a',encoding='utf-8') as f:
            f.write(f"\n- {row['Timestamp']} | {self.run_id} | {test_id} | **{status}** | {metric}: {calculated} / {reference} {unit}. {comment} {action}\n")
        level=logging.ERROR if status in ('FAIL','BLOCKED') else logging.WARNING if status in ('WARNING','NOT_VERIFIED') else logging.DEBUG
        logging.getLogger('pipeline').log(level,'HARNESS %s %s %s',test_id,status,comment)
        return row

    def compare(self,test_id,actual,expected,tol=1e-6,unit='',source='',module=''):
        return self.record(test_id,'VERIFY','PASS' if isclose(actual,expected,rel_tol=1e-10,abs_tol=tol) else 'FAIL',
                           calculated=actual,reference=expected,tolerance=tol,unit=unit,source=source,module=module)

    def verify(self,data,tco,cflp,iot,passport):
        D=lambda v:Decimal(str(v))
        for name,x in tco['baseline'].items():
            r=data.routes[name]; c=data.cargo; b=data.cbam
            with localcontext() as ctx:
                ctx.prec=35
                value=D(c.volume_tons)*D(c.price_usd_per_ton)
                freight=sum(D(l.distance_km)*D(l.tariff_usd_tkm)*D(c.volume_tons) for l in r.legs)
                et=sum(D(l.distance_km)*D(l.emission_g_tkm)/D(1e6) for l in r.legs)
                border=max(D(0),D(b.see_prod_tco2_per_ton)+et-D(b.benchmark_eu_tco2_per_ton))*D(c.volume_tons)*(D(b.p_eu_ets_eur)-D(b.p_carbon_origin_eur))*D(b.eur_usd_rate)
                total=freight+value*D(c.insurance_rate)+value*D(c.wacc_baseline)/365*sum(D(l.lead_time_days) for l in r.legs)+D(c.pack_comp_cost_usd)+D(c.p_fail_base)*D(c.l_fail_loss_usd)+border
            self.compare(name+'_decimal',x.tco_log_usd,float(total),unit='USD',source='Независимый Decimal, PDF с.3–4',module='1')
            self.compare(name+'_component_sum',x.tco_log_usd,sum([x.freight_usd,x.insurance_usd,x.inventory_usd,x.packaging_usd,x.risk_usd,x.border_usd]),unit='USD')
            self.compare(name+'_currency',x.border_usd,x.tax_cbam_eur*data.cbam.eur_usd_rate,unit='USD')
        for root in tco['sensitivity']['roots']:
            if root['status']=='CROSSING':
                self.compare(f"root_{root['a']}_{root['b']}_{root['parameter']}_{root['wacc']}",root['residual_usd'],0,1e-5,unit='USD')
                self.record('root_sign_change','VERIFY','PASS' if root['sign_left']*root['sign_right']<0 else 'FAIL',calculated=root['value'],unit=root['parameter'])
        for key,sol in cflp['solutions'].items():
            self.compare(key+'_demand',max(abs(v) for v in sol.demand_residuals.values()),0,1e-5,unit='т/год')
            self.compare(key+'_cost',sol.objective_rub_year,sol.fixed_rub_year+sol.transport_rub_year,.01,unit='руб/год')
            self.record(key+'_capacity','VERIFY','PASS' if min(sol.capacity_slacks.values())>=-.001 else 'FAIL',calculated=min(sol.capacity_slacks.values()),reference=0,tolerance=.001,unit='т/год')
        self.compare('single_enumeration',cflp['solutions']['single'].objective_rub_year,enumerate_single(data.cflp)['objective_rub_year'],.01,unit='руб/год',source='Полный перебор 4^5 назначений')
        for key,big in [('multi',False),('bigm_milp',True)]:
            self.compare(key+'_highs_enumeration',cflp['solutions'][key].objective_rub_year,enumerate_multi(data.cflp,big),.01,unit='руб/год',source='Перебор 16 открытий + SciPy/HiGHS')
        for m,l in [('multi','physical_lp'),('bigm_milp','bigm_lp')]:
            self.record(m+'_lp_bound','VERIFY','PASS' if cflp['solutions'][l].objective_rub_year<=cflp['solutions'][m].objective_rub_year+.01 else 'FAIL')
        episode=iot['temperature_incidents'][0]
        for key,a,e in [('start',episode.start_index,540),('end',episode.end_index,548),('duration',episode.duration_minutes,45),('shock',iot['shock_incidents'][0].start_index,920)]:
            self.compare('iot_'+key,a,e,source='PDF задания с.2–3; индексы 0-based')
        self.compare('dynamic_risk_delta',iot['delta_usd'],(1-data.cargo.p_fail_base)*data.cargo.l_fail_loss_usd,.00001,unit='USD')
        self.compare('dpp_tco',passport.adjusted_tco_usd,iot['after'].tco_log_usd,.005,unit='USD')
        self.compare('dpp_scope3',passport.scope3_transport_emissions_tco2,iot['scope3_transport_emissions_tco2'],.00005,unit='т CO2')
        with data.telemetry.source.open('rb') as telemetry_bytes:
            digest=hashlib.file_digest(telemetry_bytes,'sha256').hexdigest()
        self.record('telemetry_sha256','VERIFY','PASS' if passport.sha256_telemetry_digest==digest else 'FAIL',calculated=passport.sha256_telemetry_digest,reference=digest)
        # Независимая сферическая формула косинусов вместо Haversine.
        distance=0
        samples=data.telemetry.samples
        for i,seg in enumerate(iot['segments']):
            if not seg['accepted']: continue
            a,b=samples[i],samples[i+1]
            z=sin(radians(a.latitude))*sin(radians(b.latitude))+cos(radians(a.latitude))*cos(radians(b.latitude))*cos(radians(b.longitude-a.longitude))
            distance+=6371.0088*acos(min(1,max(-1,z)))
        self.compare('gps_independent_cosine',iot['distance_km'],distance,.001,unit='км')
        return self.rows
