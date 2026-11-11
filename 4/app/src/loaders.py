import csv
import json
from datetime import datetime
from pathlib import Path
from .models import (CargoProfile,CBAMParameters,TransportRoute,TransportLeg,Customer,
                     Facility,TariffMatrix,CFLPInput,TelemetrySample,TelemetryDataset,ProjectInputData)

class InputLoader:
    FILENAMES = ('module1_tco_cbam_input.json','module2_cflp_customers.csv',
                 'module2_cflp_facilities.csv','module2_cflp_tariffs.csv','module3_iot_telemetry.csv')

    @staticmethod
    def rows(path, fields=None):
        with path.open(encoding='utf-8-sig',newline='') as f:
            reader=csv.DictReader(f)
            if fields and reader.fieldnames!=fields:
                raise ValueError(f'{path.name}: неверные столбцы {reader.fieldnames}, ожидается {fields}')
            rows=list(reader)
        if not rows or any(None in r or any(v is None or not v.strip() for v in r.values()) for r in rows):
            raise ValueError(f'{path.name}: пустой файл, пропуск или неверное число полей')
        return rows

    def load(self, directory: Path) -> ProjectInputData:
        directory=Path(directory)
        def no_duplicates(pairs):
            d={}
            for k,v in pairs:
                if k in d: raise ValueError(f'Повтор ключа JSON: {k}')
                d[k]=v
            return d
        raw=json.loads((directory/self.FILENAMES[0]).read_text(encoding='utf-8-sig'),object_pairs_hook=no_duplicates)
        # JSON числа должны быть числами: никакой скрытой конверсии строк.
        cargo=CargoProfile(**raw['cargo_profile']); cbam=CBAMParameters(**raw['cbam_parameters'])
        routes={k:TransportRoute(k,v['description'],tuple(TransportLeg(**l) for l in v['legs'])) for k,v in raw['scenarios'].items()}
        cs=self.rows(directory/self.FILENAMES[1],['customer_id','name','demand_tons_year'])
        fs=self.rows(directory/self.FILENAMES[2],['facility_id','location','fixed_cost_rub_year','capacity_tons_year'])
        customers=tuple(Customer(r['customer_id'],r['name'],float(r['demand_tons_year'])) for r in cs)
        facilities=tuple(Facility(r['facility_id'],r['location'],float(r['fixed_cost_rub_year']),float(r['capacity_tons_year'])) for r in fs)
        tr=self.rows(directory/self.FILENAMES[3],['facility_id']+[c.customer_id for c in customers])
        if len({r['facility_id'] for r in tr})!=len(tr): raise ValueError('Повтор хаба в матрице тарифов')
        tariffs=TariffMatrix({(r['facility_id'],k):float(v) for r in tr for k,v in r.items() if k!='facility_id'})
        fields=['timestamp','latitude','longitude','temp_celsius','pressure_bar','accel_x_g','accel_y_g','accel_z_g']
        samples=tuple(TelemetrySample(i,datetime.fromisoformat(r['timestamp']),**{k:float(v) for k,v in r.items() if k!='timestamp'})
                      for i,r in enumerate(self.rows(directory/self.FILENAMES[4],fields)))
        return ProjectInputData(cargo,cbam,routes,CFLPInput(customers,facilities,tariffs),TelemetryDataset(samples,directory/self.FILENAMES[4]))
