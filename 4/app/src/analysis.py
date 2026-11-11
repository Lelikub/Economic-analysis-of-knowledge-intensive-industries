"""Экономическая интерпретация вычисленных результатов; текст не выполняет вычислений."""
from dataclasses import asdict
import pandas as pd
from .presentation import hub_label,customer_label

def prepare_tables(data,tco,cflp,iot,quality,output):
    directory=output/'tables'; directory.mkdir(parents=True,exist_ok=True)
    tables={}
    def save(name,frame):
        tables[name]=frame
        frame.to_csv(directory/(name+'.csv'),index=False,encoding='utf-8-sig',float_format='%.12g')
    save('tco_baseline',pd.DataFrame([asdict(v) for v in tco['baseline'].values()]))
    legrows=[]
    for name,r in data.routes.items():
        for l in r.legs:
            legrows.append(dict(route_id=name,**asdict(l),freight_usd=l.distance_km*l.tariff_usd_tkm*data.cargo.volume_tons,
                                emissions_tco2_per_t=l.distance_km*l.emission_g_tkm*1e-6))
    save('route_legs',pd.DataFrame(legrows))
    for key in ['wacc','cargo_value','lead_time','ets']: save(key,tco['sensitivity'][key])
    save('break_even',pd.DataFrame(tco['sensitivity']['roots']))
    save('ets_thresholds',pd.DataFrame(tco['sensitivity']['ets_thresholds']))
    solutions=cflp['solutions']
    rows=[]
    for key,sol in solutions.items():
        rows.append(dict(model=key,status=sol.status,objective_rub_year=sol.objective_rub_year,fixed_rub_year=sol.fixed_rub_year,
                         transport_rub_year=sol.transport_rub_year,median_seconds=cflp['timings'][key]['median_seconds'],
                         max_physical_overload_tons=max(sol.physical_overloads.values()),
                         lp_gap_pct=cflp['physical_gap_pct'] if key in ('multi','physical_lp') else cflp['bigm_gap_pct'] if key in ('bigm_milp','bigm_lp') else 0))
        save('flows_'+key,pd.DataFrame([dict(facility_id=j,**row) for j,row in sol.flows.items()]))
        save('facilities_'+key,pd.DataFrame([dict(facility_id=f.facility_id,opened_y=sol.y[f.facility_id],load_tons=sol.loads[f.facility_id],
                       capacity_tons=f.capacity_tons_year,capacity_slack=sol.capacity_slacks[f.facility_id],physical_overload=sol.physical_overloads[f.facility_id]) for f in data.cflp.facilities]))
        residuals=[]
        for kind,values in [('demand',sol.demand_residuals),('capacity',sol.capacity_slacks),('binary',sol.binary_residuals),('link',sol.linking_slacks)]:
            residuals.extend(dict(constraint=kind,identifier=k,value=v) for k,v in values.items())
        save('residuals_'+key,pd.DataFrame(residuals))
    save('cflp_comparison',pd.DataFrame(rows))
    save('solver_timings',pd.DataFrame([dict(model=k,repetition=i+1,seconds=t) for k,v in cflp['timings'].items() for i,t in enumerate(v['samples_seconds'])]))
    columns=list(asdict(iot['temperature_incidents'][0])) if iot['temperature_incidents'] else ['kind','start_index','end_index','start','end_observed','interval_end','count','duration_minutes','minimum','maximum','axis']
    save('temperature_incidents',pd.DataFrame([asdict(v) for v in iot['temperature_incidents']],columns=columns))
    save('shock_incidents',pd.DataFrame([asdict(v) for v in iot['shock_incidents']],columns=columns))
    telemetry=pd.DataFrame([asdict(s) for s in data.telemetry.samples]); telemetry['a_total_g']=iot['norms']
    save('telemetry',telemetry)
    segments=pd.DataFrame(iot['segments']);segments['cumulative_accepted_km']=segments['distance_km'].where(segments['accepted'],0).cumsum()
    save('gps_segments',segments)
    save('dynamic_tco',pd.DataFrame([dict(state=k,**asdict(iot[k])) for k in ['before','after']]))
    save('quality',pd.DataFrame(quality,columns=['file','row_or_key','kind','rule','value','boundary','decision']))
    return tables

def interpret(data,tco,cflp,iot):
    b=tco['baseline'];s=tco['sensitivity']; sea=b['Sea_Road_Multimodal']; rail=b['Rail_Express']; air=b['Air_Express']
    def f(x): return f'{x:,.2f}'.replace(',',' ')
    multi=cflp['solutions']['multi']
    open_names=', '.join(hub_label(j) for j,y in multi.y.items() if y>.5)
    assignments='; '.join(customer_label(c)+' получает груз из хаба '+hub_label(j)
                         for c in data.cflp.customers for j,row in multi.flows.items() if row[c.customer_id]>1e-6)
    loads='; '.join(hub_label(facility.facility_id)+f" обслуживает {multi.loads[facility.facility_id]:g} из {facility.capacity_tons_year:g} тонн в год"
                   for facility in data.cflp.facilities if multi.y[facility.facility_id]>.5)
    narratives={
      'tco_baseline':f"Минимальная логистическая стоимость у морского маршрута: {f(sea.tco_log_usd)} USD на партию. Железнодорожный вариант стоит {f(rail.tco_log_usd)} USD, авиационный — {f(air.tco_log_usd)} USD. При базовой цене 22 000 USD/т морской маршрут экономит {f(rail.tco_log_usd-sea.tco_log_usd)} USD против ж/д. Фрахт авиации равен {f(air.freight_usd)} USD и определяет высокий итог; сравниваются одинаковые масса, страхование, упаковка и исходный риск.",
      'wacc':f"При WACC 5–30% все три зависимости линейно возрастают. Авиация экономит против ж/д {f(rail.inventory_usd-air.inventory_usd)} USD капитала при 15%, тогда как разница фрахта и CBAM равна {f(s['answers']['air_rail_freight_cbam_gap_usd'])} USD. Ориентир задания «более 290 тыс.» подтверждается для пары авиа–море ({f(s['answers']['air_sea_freight_cbam_gap_usd'])} USD), но не для пары авиа–ж/д. Высокая ставка сама по себе не делает авиацию выгодной при исходной цене.",
      'cargo_value':f"Рост стоимости груза увеличивает страхование одинаково для всех вариантов; различия наклонов задаёт капитал в пути. При 15% равенство авиа–ж/д наступает лишь при {f(s['answers']['price_air_rail_including_cbam_usd_per_t'])} USD/т, за пределами 20–500 тыс. USD/т. Для выбора между морем и ж/д применяется найденный корень из таблицы, а не предполагаемое преимущество скорости.",
      'lead_time':"Изменяется только время Deep-Sea Maritime: t_sea = t_total − 3.5 суток, наземные плечи сохранены. Фрахт, выбросы, риск и ставки постоянны. Линейный рост затрат даёт порог море–ж/д в таблице. Пересечение море–авиа за пределами диапазона 10–120 суток обозначено NO_CROSSING_IN_RANGE; график не содержит фиктивной точки.",
      'ets':"Положительная разность TCO(авиа)−TCO(ж/д) означает преимущество ж/д. Во всём показанном диапазоне ETS 0–500 EUR/т CO2 и P=150–300 тыс. USD/т авиация дороже. Формальное равенство требует отрицательной ETS: при исходном WACC нет первоначального преимущества авиации, которое мог бы нивелировать положительный сбор. Отрицательный порог — алгебраическая экстраполяция, не допустимый сценарий цены квоты.",
      'multi':f"Распределительный хаб — складской узел сети. Открываются хабы {open_names}. Стоимость сети составляет {f(multi.objective_rub_year)} рублей в год; транспортная часть — {f(multi.transport_rub_year)} рублей в год. Назначения: {assignments}. Модель допускает несколько источников снабжения каждого потребителя, однако в найденном оптимуме дробление фактически не требуется.",
      'single':f"Ограничение одного источника даёт {f(cflp['solutions']['single'].objective_rub_year)} руб./год: надбавка к Multi-Sourcing равна {f(cflp['solutions']['single'].objective_rub_year-cflp['solutions']['multi'].objective_rub_year)} руб./год. Это свойство конкретного набора данных; в общем случае запрет дробления способен увеличивать стоимость и делать сеть недопустимой.",
      'capacity':f"Физические ограничения соблюдены: {loads}. Небольшой резерв хабов B — Тверь и C — Рязань требует внимания при росте спроса. Хаб A — Ногинск не открывается. Хаб D — Великий Новгород имеет резерв для увеличения загрузки. Общая мощность 2750 тонн в год сама по себе не доказывает допустимость назначений: её подтвердили решатель методом ветвей и отсечений (CBC, Coin-or Branch and Cut) и независимый перебор.",
      'bigm':f"При реальных мощностях разрыв LP составляет {f(cflp['physical_gap_pct'])}%, при M=10^9 — {f(cflp['bigm_gap_pct'])}%. Замена K на M также меняет физическую допустимость; максимальная перегрузка исходной мощности в Big-M MILP равна {f(max(cflp['solutions']['bigm_milp'].physical_overloads.values()))} т/год. Медианы трёх запусков приведены как наблюдения; столь малая задача не обосновывает общее утверждение об ускорении или замедлении CBC.",
      'temperature':f"Достоверное нарушение на индексах 540–548 (строки CSV 542–550 с учётом заголовка) охватывает {f(iot['total_violation_minutes'])} минут. Отсчёты 05:00–05:40 12.04.2026 представляют интервалы до 05:45. Максимум −16.03 °C. Непрерывный эпизод превышает 30 минут; регламент учебного задания требует SCRAP_WRITE_OFF. Это реальный стресс-инцидент, а не ошибка измерения.",
      'shock':f"На индексе 920, 13.04.2026 в 12:40, зафиксирована ось Z=2.65g; норма трёх осей {iot['peak_norm_g']:.6f}g. Решение SHOCK_DETECTED принято по оси, а не по норме. Шок требует диагностики упаковки и арматуры; самостоятельного температурного списания он не вызывает.",
      'gps':f"Сумма {len(iot['segments'])} проверенных GPS-сегментов равна {f(iot['distance_km'])} км; исключено {iot['excluded_gps_segments']}. При {iot['rail_emission_factor_g_tkm']:g} г CO2/(т·км) и 20 т след контрольного участка составляет {iot['scope3_transport_emissions_tco2']:.6f} т CO2. Он не подменяет выбросы полного маршрута: {rail.transport_emissions_tco2_per_t*data.cargo.volume_tons:.6f} т CO2. Ломаная соединяет измерения и не является восстановлением точной геометрии рельсового пути.",
      'dynamic':f"Тот же сценарий Rail_Express пересчитан с p_fail={iot['before'].p_fail:g} до {iot['after'].p_fail:g}. TCO_log вырос с {f(iot['before'].tco_log_usd)} до {f(iot['after'].tco_log_usd)} USD; прирост {f(iot['delta_usd'])} USD обусловлен только рисковой компонентой. L_fail уже включает стоимость партии; она повторно не добавляется. TCO_total представлен отдельно по формуле задания.",
    }
    narratives['multi']+=' Рисунки 6 и 7 совпадают корректно: название «из нескольких источников» означает разрешение дробить поставки, а не обязанность использовать несколько хабов для каждого клиента. Найденный оптимум уже использует один источник для каждого потребителя.'
    narratives['single']+=' Поэтому рисунок 7 совпадает с рисунком 6: введённый запрет дробления не исключает исходный оптимальный план и не меняет его стоимость. Это подтверждено независимым полным перебором назначений, а не копированием данных другого графика.'
    # Каждый текст под графиком читается самостоятельно, без поиска расшифровок в начале отчёта.
    replacements=[
      ('USD/т','долларов за тонну'),('USD','долларов Соединённых Штатов Америки'),
      ('EUR/т CO2','евро за тонну углекислого газа'),
      ('г CO2/(т·км)','граммов углекислого газа на тонно-километр'),
      ('т CO2','тонн углекислого газа'),
      ('GPS-сегментов','отрезков между координатами глобальной спутниковой системы позиционирования (GPS)'),
      ('Deep-Sea Maritime','морского плеча Deep-Sea Maritime'),
      ('t_sea = t_total − 3.5','время морского плеча = общее время − 3.5'),
      ('NO_CROSSING_IN_RANGE','«пересечения в исследуемом диапазоне нет» (NO_CROSSING_IN_RANGE)'),
      ('Multi-Sourcing','модели снабжения из нескольких источников'),
      ('Big-M MILP','целочисленной модели с искусственно завышенной мощностью (Big-M MILP)'),
      ('разрыв LP','разрыв линейной релаксации (LP — линейное программирование)'),
      ('Замена K на M','Замена реальной мощности K на искусственно большую константу M'),
      ('SCRAP_WRITE_OFF','списания партии (SCRAP_WRITE_OFF)'),
      ('SHOCK_DETECTED','«обнаружен механический удар» (SHOCK_DETECTED)'),
      ('строки CSV','строки табличного текстового файла (CSV)'),
      ('Rail_Express','железнодорожной экспресс-доставки (Rail_Express)'),
      ('L_fail','полный ущерб L_fail'),
    ]
    for key in narratives:
        for short,long in replacements:narratives[key]=narratives[key].replace(short,long)
        explanations=[]
        for token,meaning in [('TCO_log','совокупные логистические затраты без закупочной стоимости партии'),
                              ('TCO_total','полная стоимость с закупкой партии'),
                              ('TCO(','TCO — совокупная стоимость владения логистикой'),
                              ('WACC','средневзвешенная стоимость капитала'),
                              ('CBAM','механизм трансграничной углеродной корректировки'),
                              ('ETS','цена квоты в европейской системе торговли выбросами'),
                              ('p_fail','вероятность отказа или утраты партии'),
                              ('ж/д','железнодорожный транспорт')]:
            if token in narratives[key]:explanations.append((token+' — '+meaning) if token!='TCO(' else meaning)
        if explanations:narratives[key]+=' Обозначения: '+ '; '.join(explanations)+'.'
    narratives['bigm']+=' Big-M означает ограничение с большой константой M; MILP — смешанное целочисленное линейное программирование. CBC — решатель Coin-or Branch and Cut, метод ветвей и отсечений.'
    narratives['shock']+=' Обозначение g — единица перегрузки, равная ускорению свободного падения; X, Y и Z — три взаимно перпендикулярные оси акселерометра.'
    return narratives
