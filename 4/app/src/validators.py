from dataclasses import fields
from math import isfinite
from .models import ProjectInputData

class DataValidator:
    @staticmethod
    def numeric(value, name, low=0, high=None, strict=False):
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not isfinite(value):
            raise ValueError(f'{name}: DATA_ERROR не конечное числовое значение: {value!r}')
        if value<low or (strict and value==low) or (high is not None and value>high):
            raise ValueError(f'{name}: DATA_ERROR {value} за границами {low}..{high}')

    def validate(self,d:ProjectInputData,expected_dataset=True):
        issues=[]; c=d.cargo
        for f in fields(c):
            if f.name=='material_name': continue
            fraction=f.name in ('insurance_rate','wacc_baseline','p_fail_base')
            self.numeric(getattr(c,f.name),f'cargo.{f.name}',high=1 if fraction else None,strict=not fraction)
        for f in fields(d.cbam): self.numeric(getattr(d.cbam,f.name),f'cbam.{f.name}',strict=f.name=='eur_usd_rate')
        if d.cbam.p_eu_ets_eur<d.cbam.p_carbon_origin_eur:
            issues.append(self.issue('module1_tco_cbam_input.json','cbam_parameters','WARNING','ETS>=origin',d.cbam.p_eu_ets_eur,'origin','Формула задания допускает отрицательный сбор; сохранён без отсечения'))
        if set(d.routes)!={'Air_Express','Rail_Express','Sea_Road_Multimodal'}: raise ValueError('Набор маршрутов неполон')
        for name,r in d.routes.items():
            if r.route_id!=name or len(r.legs)!=3: raise ValueError(f'{name}: ожидаются три плеча и согласованный ID')
            for leg in r.legs:
                for f in fields(leg):
                    if f.name!='name': self.numeric(getattr(leg,f.name),f'{name}.{leg.name}.{f.name}',strict=f.name!='lead_time_days')
        cf=d.cflp; customers={x.customer_id for x in cf.customers}; facilities={x.facility_id for x in cf.facilities}
        if len(customers)!=len(cf.customers) or len(facilities)!=len(cf.facilities): raise ValueError('Повтор IDs CFLP')
        for x in cf.customers: self.numeric(x.demand_tons_year,x.customer_id,strict=True)
        for x in cf.facilities:
            self.numeric(x.capacity_tons_year,x.facility_id+'.capacity',strict=True)
            self.numeric(x.fixed_cost_rub_year,x.facility_id+'.fixed',strict=True)
        if set(cf.tariffs.values)!={(j,i) for j in facilities for i in customers}: raise ValueError('Несовместимые IDs/прямоугольность тарифов')
        for k,v in cf.tariffs.values.items(): self.numeric(v,str(k),strict=True)
        if expected_dataset and (len(customers)!=5 or len(facilities)!=4 or sum(x.demand_tons_year for x in cf.customers)!=1600 or sum(x.capacity_tons_year for x in cf.facilities)!=2750):
            raise ValueError('Контроль состава CFLP: ожидается 5/4 и 1600/2750 т/год')
        samples=d.telemetry.samples
        if not samples: raise ValueError('Пустая телеметрия')
        if expected_dataset and len(samples)!=1440: raise ValueError('Ожидается 1440 записей')
        self.numeric(d.telemetry.interval_minutes,'interval_minutes',strict=True)
        for n,s in enumerate(samples):
            for f in fields(s):
                if f.name not in ('index','timestamp'):
                    value=getattr(s,f.name)
                    if not isinstance(value,(int,float)) or not isfinite(value): raise ValueError(f'IoT[{n}].{f.name}: NaN/inf')
            if not -90<=s.latitude<=90 or not -180<=s.longitude<=180: raise ValueError(f'IoT[{n}]: неверные координаты')
            self.numeric(s.pressure_bar,f'IoT[{n}].pressure',strict=True)
            if not -273.15<s.temp_celsius<200: raise ValueError(f'IoT[{n}]: физически невозможная температура')
            if max(abs(s.accel_x_g),abs(s.accel_y_g),abs(s.accel_z_g))>100: raise ValueError(f'IoT[{n}]: невалидная перегрузка >100g')
            if n:
                minutes=(s.timestamp-samples[n-1].timestamp).total_seconds()/60
                if minutes<=0: raise ValueError('Временные метки не возрастают / дубликаты')
                if minutes!=d.telemetry.interval_minutes:
                    issues.append(self.issue(d.telemetry.source.name,n+2,'WARNING','шаг 5 минут',minutes,5,'Разрыв эпизода; недостающие интервалы не интерполируются'))
        return issues

    @staticmethod
    def issue(file,key,kind,rule,value,boundary,decision):
        return dict(file=file,row_or_key=str(key),kind=kind,rule=rule,value=value,boundary=boundary,decision=decision)
