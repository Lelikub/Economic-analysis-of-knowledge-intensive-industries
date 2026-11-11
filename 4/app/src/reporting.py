from pathlib import Path
import json
import zipfile
from collections import Counter
from lxml import etree
import pandas as pd
from docx import Document
from docx.shared import Cm,Pt,RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from .presentation import GLOSSARY,DPP_FIELDS,hub_label,customer_label,route_label,status_label,MODEL_NAMES

REPORT_NAME='Итоговый_отчет_практическая_4_ЭА.docx'

def fmt(value):
    if value is None or (isinstance(value,float) and pd.isna(value)): return '—'
    if isinstance(value,float): return f'{value:,.2f}'.replace(',',' ').replace('.',',')
    return str(value)

class ReportBuilder:
    def __init__(self,output,template=None):
        self.output=Path(output);self.template=Path(template) if template else None

    def build(self,data,metrics,plots,narratives,tests,harness_rows,source_files):
        doc=Document(str(self.template)) if self.template and self.template.exists() else Document()
        for child in list(doc._element.body):
            if child.tag!=qn('w:sectPr'): doc._element.body.remove(child)
        section=doc.sections[0]
        section.page_width=Cm(21);section.page_height=Cm(29.7)
        section.top_margin=Cm(1.7);section.bottom_margin=Cm(1.7);section.left_margin=Cm(2.2);section.right_margin=Cm(1.7)
        normal=doc.styles['Normal'];normal.font.name='Times New Roman';normal.font.size=Pt(12)
        normal.paragraph_format.line_spacing=1.15;normal.paragraph_format.first_line_indent=Cm(1.25)
        normal.paragraph_format.space_after=Pt(5)
        normal.paragraph_format.page_break_before=False
        for name,size in [('Heading 1',15),('Heading 2',13)]:
            s=doc.styles[name];s.font.name='Times New Roman';s.font.size=Pt(size);s.font.color.rgb=RGBColor.from_string('193B60');s.font.bold=True
            s.paragraph_format.keep_with_next=True;s.paragraph_format.first_line_indent=Cm(0)
            s.paragraph_format.page_break_before=False
        for s in section.header.paragraphs+section.footer.paragraphs: s.clear()
        foot=section.footer.paragraphs[0];foot.alignment=WD_ALIGN_PARAGRAPH.CENTER
        field=OxmlElement('w:fldSimple');field.set(qn('w:instr'),'PAGE');foot._p.append(field)
        def p(text,style=None):
            paragraph=doc.add_paragraph(str(text),style)
            paragraph.alignment=WD_ALIGN_PARAGRAPH.JUSTIFY
            return paragraph
        def heading(text,level=1): return doc.add_heading(text,level)
        def page(): doc.add_page_break()
        def table(headers,rows):
            t=doc.add_table(rows=1,cols=len(headers));t.style='Table Grid'
            for cell,text in zip(t.rows[0].cells,headers): cell.text=str(text)
            repeat=OxmlElement('w:tblHeader');t.rows[0]._tr.get_or_add_trPr().append(repeat)
            for row in rows:
                cells=t.add_row().cells
                for cell,value in zip(cells,row): cell.text=fmt(value)
            for i,row in enumerate(t.rows):
                no_split=OxmlElement('w:cantSplit');row._tr.get_or_add_trPr().append(no_split)
                for cell in row.cells:
                    for para in cell.paragraphs:
                        para.paragraph_format.first_line_indent=Cm(0);para.paragraph_format.space_after=Pt(2);para.paragraph_format.space_before=Pt(2)
                        for run in para.runs:
                            run.font.name='Times New Roman';run.font.size=Pt(9)
                            if i==0: run.font.bold=True;run.font.color.rgb=RGBColor(255,255,255)
                    if i==0:
                        shade=OxmlElement('w:shd');shade.set(qn('w:fill'),'193B60');cell._tc.get_or_add_tcPr().append(shade)
            return t
        def image(key):
            meta=next(x for x in plots if x['key']==key)
            paragraph=doc.add_paragraph();paragraph.paragraph_format.first_line_indent=Cm(0);paragraph.alignment=WD_ALIGN_PARAGRAPH.CENTER
            paragraph.paragraph_format.keep_with_next=True
            paragraph.add_run().add_picture(str(self.output/'figures'/(key+'.png')),width=Cm(16.7))
            cap=doc.add_paragraph(f"Рисунок {meta['number']} — {meta['title']}. Источник: {meta['source']}.")
            cap.paragraph_format.first_line_indent=Cm(0);cap.paragraph_format.keep_with_next=True
            for r in cap.runs: r.font.size=Pt(9)
        def analysis(key):
            p(narratives[key])
            if key=='tco_baseline':p('Обозначение на рисунке: CBAM — механизм трансграничной углеродной корректировки; соответствующий столбец показывает учебный трансграничный углеродный сбор. Логистические затраты не включают закупочную стоимость самой партии.')
            if key in ('multi','single','capacity'):
                p('Расшифровка хабов: '+ '; '.join(hub_label(f.facility_id,full=True) for f in data.cflp.facilities)+'.')
            if key in ('multi','single'):
                p('Номера потребителей на рисунке: '+ '; '.join(customer_label(c) for c in data.cflp.customers)+'.')
        # Титул не содержит вымышленных имён или незаполненных полей шаблона.
        for text in ['МИНИСТЕРСТВО НАУКИ И ВЫСШЕГО ОБРАЗОВАНИЯ РОССИЙСКОЙ ФЕДЕРАЦИИ','Российский химико-технологический университет имени Д.И. Менделеева']:
            z=p(text);z.alignment=WD_ALIGN_PARAGRAPH.CENTER
        doc.add_paragraph('\n\n')
        z=heading('Практическая работа № 4');z.alignment=WD_ALIGN_PARAGRAPH.CENTER
        z=p('Инженерно-экономическое моделирование мультимодальной логистики High-Tech химии: TCO, трансграничные барьеры и пространственная оптимизация');z.alignment=WD_ALIGN_PARAGRAPH.CENTER
        p('Дисциплина: «Экономический анализ наукоёмких производств».')
        p('Составитель задания: доцент, кандидат технических наук Потапов Григорий Геннадиевич.')
        p('Расчётный отчёт подготовлен программно. Сведения об исполнителе и учебной группе в исходных данных не заданы.')
        p('Дата расчёта: 25.10.2026. Москва, 2026.')
        page();heading('Содержание')
        for x in ['1. Цель, источники и архитектура','2. Контроль данных и методика','3. TCO / CBAM и чувствительность','4. Оптимизация сети CFLP','5. Телеметрия, динамический TCO и DPP','6. Ответы на контрольные вопросы','7. Проверка, Harness Log и воспроизводимость','8. Итоги и источники']:p(x)
        heading('1. Цель, источники и архитектура')
        p('Цель — сравнить три логистических маршрута партии HF массой 20 т, оптимизировать сеть химических хабов и связать физические инциденты телеметрии с финансовым риском и цифровым паспортом партии.')
        p('Совокупная стоимость владения логистикой (TCO, Total Cost of Ownership), средневзвешенная стоимость капитала (WACC, Weighted Average Cost of Capital) и механизм трансграничной углеродной корректировки (CBAM, Carbon Border Adjustment Mechanism) рассчитываются по учебным формулам задания, с. 3–5, и лекции 7, с. 7–11. Расширенный CBAM с транспортным следом не объявляется действующей правовой методикой для HF.')
        p('Задача размещения мощностей с ограничениями (CFLP, Capacitated Facility Location Problem) решается как смешанная целочисленная линейная модель (MILP). Модель с единственным источником снабжения — SSCFLP; линейная релаксация — LP. Решатель CBC (Coin-or Branch and Cut) вызывается через PuLP. Интернет вещей (IoT) передаёт данные в цифровой паспорт продукта (DPP).')
        p('Архитектура: PipelineCLI → SprintController → PipelineOrchestrator → TCOService / CFLPService / TelemetryService / PassportService → типизированные объекты данных и независимые калькуляторы. Отчёт получает готовые метрики; графики читают сохранённые CSV.')
        table(['Стадии конвейера','Результат'],[
          ['PREPARE → LOAD → VALIDATE_INPUT → BUILD_MODELS','Версии, SHA-256, проверенные предметные объекты'],
          ['CALCULATE_TCO → SOLVE_CFLP → PROCESS_IOT','TCO, MILP/LP, эпизоды, динамический риск'],
          ['GENERATE_DPP → VERIFY','Паспорт, независимые сверки, pytest'],
          ['PLOT_AND_VALIDATE → BUILD_REPORT → FINAL_AUDIT','PNG, Word, контроль артефактов и манифест']])
        p('Порядок стадий: подготовка → загрузка → проверка входных данных → сборка моделей → расчёт логистической стоимости → оптимизация сети складов → обработка телеметрии → создание цифрового паспорта → независимая проверка → графики → отчёт → итоговый аудит. Технические имена классов, файлов и стадий приведены для воспроизводимости.')
        heading('1.1. Расшифровка сокращений и обозначений',2)
        p('Сокращения в формулах, таблицах и технических идентификаторах раскрыты ниже. Под графиками повторяются обозначения, необходимые для самостоятельного чтения каждого блока.')
        table(['Сокращение / обозначение','Полное наименование и смысл'],GLOSSARY)
        heading('1.2. Справочник хабов и потребителей',2)
        p('Хаб — распределительный складской узел. Буквы A, B, C, D — идентификаторы площадок из исходных файлов; в отчёте рядом с ними указаны города.')
        table(['Код и расположение хаба','Мощность, тонн в год'],[[hub_label(f.facility_id,full=True),f.capacity_tons_year] for f in data.cflp.facilities])
        table(['Потребитель','Спрос, тонн в год'],[[customer_label(c),c.demand_tons_year] for c in data.cflp.customers])
        heading('2. Контроль данных и методика')
        table(['Источник','Состав','SHA-256 (полный — в манифесте)'],[[k,('1440 × 8' if k.endswith('telemetry.csv') else str(v['bytes'])+' байт'),v['sha256'][:16]+'…'] for k,v in source_files.items() if k.startswith('module')])
        p('Первичные JSON/CSV сохранены без изменений. RAR проверен побайтовыми хэшами содержимого без распаковки на диск; результаты — archive_comparison.json. Тарифная матрица ориентирована строками по хабам и столбцами по потребителям; рубли CFLP не смешиваются с долларами TCO.')
        p('Проверены типы, конечность, положительность, доли ставок, схема и уникальность идентификаторов, прямоугольность тарифов, спрос 1600 т/год, мощности 2750 т/год, 1440 временных меток и шаг 5 минут. Имена файлов и правила с фактическими значениями приведены в tables/quality.csv.')
        q=metrics['quality']
        table(['Класс','Правило / наблюдение','Решение'],[[status_label(x['kind']),f"{x['row_or_key']}: {x['rule']} = {x['value']}",x['decision']] for x in q])
        heading('2.1. Формулы и размерности',2)
        formulas=[
          ('C_freight = Σ D_m · T_m · V','D — км; T — USD/(т·км); V — т. Результат USD.'),
          ('C_ins = V · P · r_ins; C_inv = V · P · WACC · Σt_m / 365','P — USD/т; r_ins и WACC — доли; t — сутки. Результат USD.'),
          ('C_risk = p_fail · L_fail','L_fail — совокупный ущерб, USD; упаковка — исходная фиксированная сумма USD.'),
          ('E_transport = Σ D_m · E_m · 10⁻⁶','E_m — г CO2/(т·км); результат — т CO2/т груза.'),
          ('Tax_CBAM = max(0, SEE_prod + E_transport − Benchmark) · V · (ETS − Origin)','Удельные выбросы — т CO2/т; цены углерода — EUR/т CO2; результат EUR.'),
          ('C_border = Tax_CBAM · EUR_USD','Курс USD/EUR; результат USD. Отрицательный ценовой спред не отсекается формулой задания.'),
          ('TCO_log = C_freight + C_ins + C_inv + C_pack + C_risk + C_border','TCO_total = V·P + TCO_log, отдельная дополнительная метрика, USD.'),
        ]
        for formula,explanation in formulas:
            z=p(formula);z.alignment=WD_ALIGN_PARAGRAPH.CENTER
            for r in z.runs:r.font.name='Cambria Math';r.font.size=Pt(11)
            p(explanation+' Источник: задание, с. 3–4; лекция 7, с. 7–11.')
        heading('3. TCO / CBAM и чувствительность')
        b=metrics['tco']['baseline']
        table(['Компонента, USD/партию','Авиа','Ж/д','Море + авто'],[[label]+[b[k][field] for k in b] for field,label in [('freight_usd','Фрахт'),('insurance_usd','Страхование'),('inventory_usd','Капитал в пути'),('packaging_usd','Упаковка'),('risk_usd','Риск'),('border_usd','CBAM'),('tco_log_usd','Итого TCO_log'),('tco_total_usd','TCO_total с закупкой')]])
        image('01_tco');analysis('tco_baseline')
        table(['Маршрут','Время, суток','Транспорт, т CO2/т','Углеродный сбор, евро'],[[route_label(k),v['lead_time_days'],v['transport_emissions_tco2_per_t'],v['tax_cbam_eur']] for k,v in b.items()])
        for key,title,figure in [('wacc','3.1. Стоимость капитала','02_wacc'),('cargo_value','3.2. Цена груза и безубыточность','03_price'),('lead_time','3.3. Время морского маршрута','04_lead')]:
            heading(title,2);df=pd.read_csv(self.output/'tables'/(key+'.csv'))
            subset=df.iloc[[0,len(df)//2,len(df)-1]]
            table([{'wacc':'WACC, доля','cargo_value':'P, USD/т','lead_time':'Общий срок, сутки'}[key],'Авиа, USD','Ж/д, USD','Море, USD'],subset.values.tolist())
            image(figure);analysis(key)
            if key!='wacc':
                roots=[r for r in metrics['tco']['sensitivity']['roots'] if r['parameter']==('price_usd_per_t' if key=='cargo_value' else 'sea_total_days') and r['wacc']==.15]
                table(['Пара','Статус в диапазоне','Корень','За диапазоном'],[[route_label(r['a'])+' / '+route_label(r['b']),status_label(r['status']),r['value'],r['extrapolated_value'] if r['value'] is None else None] for r in roots])
                p('Точные корни, остатки подстановки и смена знака разности сохранены в break_even.csv. За диапазоном значения являются экстраполяцией линейной модели.')
        heading('3.4. Чувствительность к цене EU ETS',2)
        table(['P, USD/т','Δфрахт, USD','Экономия капитала, USD','ETS равенства, EUR/т'],[[r['price_usd_per_t'],r['freight_delta_usd'],r['capital_saving_usd'],r['ets_equality_eur']] for r in metrics['tco']['sensitivity']['ets_thresholds']])
        image('05_ets');analysis('ets')
        heading('4. Оптимизация сети CFLP')
        p('Источник: задание, с. 5–7; лекция 7, с. 19, 23. Цель min ΣF_j y_j + Σc_ij x_ij, руб./год. Для каждого потребителя Σ_j x_ij=d_i, для каждого склада Σ_i x_ij≤K_j y_j, y бинарны, x≥0. Для SSCFLP: x_ij=d_i z_ij, Σ_j z_ij=1, z_ij≤y_j, z бинарны.')
        for key,title,figure in [('multi','4.1. Multi-Sourcing','06_multi'),('single','4.2. Single-Sourcing','07_single')]:
            heading(title,2);x=metrics['cflp']['solutions'][key]
            table(['Результат решателя','Фиксированные, руб./год','Транспорт, руб./год','Итого, руб./год'],[[status_label(x['status']),x['fixed_rub_year'],x['transport_rub_year'],x['objective_rub_year']]])
            df=pd.read_csv(self.output/'tables'/('flows_'+key+'.csv'));df['facility_id']=df['facility_id'].map(hub_label)
            table(['Хаб']+list(df.columns[1:]),df.values.tolist())
            image(figure);analysis(key)
        audit=metrics['cflp']['sourcing_audit'];base=audit['baseline'];diagnostic=audit['diagnostic']
        heading('Почему рисунки 6 и 7 совпадают',2)
        p('Проверены две разные математические постановки и два разных файла потоков. В модели с несколькими источниками объёмы поставок непрерывны и дробление разрешено. В модели с одним источником назначения бинарны, а весь спрос клиента связан с единственным хабом. Оптимум первой модели оказался допустимым и для второй; следовательно, при запрете дробления оптимальная стоимость здесь не возрастает.')
        table(['Независимая проверка','Результат, рублей в год'],[
            ['Несколько источников: перебор всех наборов открытых хабов и независимое линейное решение',base['independent_multi_rub_year']],
            ['Один источник: полный перебор 1024 назначений',base['independent_single_rub_year']],
            ['Минимальная нижняя граница затрат по всем наборам хабов',base['minimum_lower_bound_rub_year']],
        ])
        p('Для каждого набора хабов отдельно рассчитана нижняя граница: фиксированные затраты плюс доставка каждого клиента по самому дешёвому тарифу среди этих хабов без ограничения их мощности. Дополнительное ограничение мощности может только повысить затраты. Найденный план достигает минимальной такой границы и соблюдает мощности; это независимо подтверждает его оптимальность. В плане B — Тверь загружена на 680 из 700 тонн в год, C — Рязань на 540 из 550, D — Великий Новгород на 380 из 650. Поэтому ни одному клиенту не приходится делить поставку.')
        table(['Сценарий проверки','Несколько источников, рублей в год','Один источник, рублей в год'],[
            ['Первичные данные: B — Тверь, 700 тонн в год',base['multi_rub_year'],base['single_rub_year']],
            ['Только диагностика: B — Тверь, 650 тонн в год',diagnostic['multi_rub_year'],diagnostic['single_rub_year']],
        ])
        p(f"Контрольное уменьшение мощности Твери выполнено только в памяти, без изменения исходного файла. При разрешённом дроблении Зеленоград получает 410 тонн из Твери и 10 тонн из Рязани; Дубна — 240 тонн из Твери и 20 тонн из Великого Новгорода. При запрете дробления весь спрос Дубны, 260 тонн, переходит в Великий Новгород. Надбавка запрета дробления составляет {fmt(diagnostic['extra_cost_single_rub_year'])} рублей в год. Обе стоимости также независимо проверены. Значит, модели действительно различаются; одинаковые базовые графики не являются ошибкой расчёта или визуализации.")
        heading('4.3. Мощности и резервы',2)
        x=metrics['cflp']['solutions']['multi']
        table(['Хаб','Открытие y','Мощность, т/год','Загрузка, т/год','Резерв, т/год'],[[hub_label(f.facility_id),x['y'][f.facility_id],f.capacity_tons_year,x['loads'][f.facility_id],x['capacity_slacks'][f.facility_id]] for f in data.cflp.facilities])
        image('08_capacity');analysis('capacity')
        heading('4.4. Big-M и LP-релаксация',2)
        comp=pd.read_csv(self.output/'tables/cflp_comparison.csv')
        comp['model']=comp['model'].map(MODEL_NAMES)
        table(['Модель','Цель, руб./год','Постоянная часть, руб./год','Разрыв, %','Медиана, с'],comp[['model','objective_rub_year','fixed_rub_year','lp_gap_pct','median_seconds']].values.tolist())
        image('09_bigm');analysis('bigm')
        lp=metrics['cflp']['solutions']['bigm_lp']
        table(['Хаб','Степень открытия y','Поток, т/год','Постоянная часть, руб./год'],[[hub_label(f.facility_id),f"{lp['y'][f.facility_id]:.9g}",lp['loads'][f.facility_id],lp['y'][f.facility_id]*f.fixed_cost_rub_year] for f in data.cflp.facilities])
        p('Gap_LP = |Z_MILP−Z_LP| / |Z_MILP| × 100%. При обоих нулевых значениях gap=0; при нулевом MILP и ненулевом LP показатель не определён. Дробные y≈поток/10⁹ искусственно уменьшают фиксированную часть. Время измерено perf_counter вокруг CBC, три повторения каждого варианта, один последовательный процесс, без параллельных потоков.')
        for key,title,figure,filename in [('temperature','5.1. Холодовая цепь','10_temperature','temperature_incidents'),('shock','5.2. Вибрационный инцидент','11_shock','shock_incidents')]:
            heading('5. Телеметрия, динамический TCO и DPP' if key=='temperature' else title)
            if key=='temperature':heading(title,2)
            df=pd.read_csv(self.output/'tables'/(filename+'.csv'))
            table(['Начальный индекс','Последний индекс','Начало','Отсчётов','Минут','Пик'],df[['start_index','end_index','start','count','duration_minutes','maximum']].values.tolist())
            image(figure);analysis(key)
            if key=='temperature':p('Политика длительности: каждый отсчёт представляет полуинтервал [t,t+5 минут). Последний отсчёт также покрывает номинальные 5 минут; пропуск или нарушение шага разрывает эпизод, неизвестное время не интерполируется. Поэтому ряд из 1440 точек имеет наблюдаемый размах 119 ч 55 мин и номинальное покрытие 120 ч. Время источника не снабжено часовым поясом и не преобразуется.')
        heading('5.3. GPS и транспортный Scope 3',2)
        iot=metrics['iot']
        table(['Показатель','Значение','Единица'],[['Сегментов',len(iot['segments']),'шт.'],['Путь',iot['distance_km'],'км'],['Исключено скачков',iot['excluded_gps_segments'],'шт.'],['Коэффициент ж/д',iot['rail_emission_factor_g_tkm'],'г CO2/(т·км)'],['Scope 3 участка',iot['scope3_transport_emissions_tco2'],'т CO2']])
        image('12_gps');analysis('gps')
        p('Haversine: d=2R atan2(√a,√(1−a)); a=sin²(Δφ/2)+cosφ₁cosφ₂sin²(Δλ/2), R=6371.0088 км. Scope3=D×E_rail×10⁻⁶×V. Порог контроля GPS — 200 км/ч, консервативное допущение качества; невозможные сегменты исключаются с DATA_ERROR, путь становится частичным, без соединения через пропуск. Источник: задание, с. 9.')
        heading('5.4. Динамический TCO и паспорт партии',2)
        table(['Сценарий','p_fail','Риск, USD','TCO_log, USD','TCO_total, USD'],[[k,iot[k]['p_fail'],iot[k]['risk_usd'],iot[k]['tco_log_usd'],iot[k]['tco_total_usd']] for k in ['before','after']])
        p(narratives['dynamic'])
        p('Цифровой паспорт продукта (DPP, Digital Product Passport) связывает номер партии, состояние перевозки, контрольную сумму файла и финансовый результат. Технические имена полей сохранены для сопоставления с исходным форматом, их смысл раскрыт в таблице.')
        table(['Поле цифрового паспорта','Расшифровка и единицы','Фактическое значение'],[[k,DPP_FIELDS.get(k,k),str(v)] for k,v in metrics['dpp'].items()])
        p('SHA-256 вычислен от исходных бинарных байт CSV и повторно проверен независимым hashlib.file_digest. Совпадение хэша подтверждает целостность конкретного файла; оно не подтверждает калибровку датчиков и происхождение данных. Показатели полного маршрута и контрольного участка разделены.')
        heading('6. Ответы на контрольные вопросы')
        heading('6.1. Экономика оборотного капитала',2)
        p('Вопрос 1 из задания: почему при высокой стоимости капитала (WACC более 20% годовых) учёт только прямых транспортных затрат не отражает экономическую целесообразность? При каком сочетании цены груза за тонну и ставки капитала сокращение времени в пути перекрывает дорогой авиафрахт и углеродный сбор?')
        p('Прямой тариф не отражает альтернативные издержки замороженного V·P. Критерий выигрыша скорости: V·P·WACC·Δt/365 > Δфрахт + ΔCBAM при остальных равных компонентах. Поэтому значимо произведение P·WACC и разница сроков, а не только WACC>20%. Источник: задание, с. 10; лекция 7, с. 9.')
        p('Здесь V — масса партии, P — цена тонны, Δt — сэкономленные сутки; WACC — средневзвешенная стоимость капитала; CBAM — механизм трансграничной углеродной корректировки. Плата за один день отвлечения капитала равна стоимости партии, умноженной на годовую ставку и делённой на 365. Страхование, упаковка и исходная вероятность потерь одинаковы у маршрутов и при попарном сравнении сокращаются.')
        answers=metrics['tco']['sensitivity']['answers']
        table(['Ставка капитала','Авиа = железная дорога, долларов/тонну','Авиа = море, долларов/тонну','Авиа дешевле обоих выше, долларов/тонну'],
              [[f"{r['wacc']:.0%}",r['air_vs_rail_price_usd_per_t'],r['air_vs_sea_price_usd_per_t'],r['air_globally_cheaper_above_usd_per_t']] for r in answers['control1_thresholds']])
        p('Например, при ставке 25% авиация начинает выигрывать у обоих альтернативных маршрутов только при цене выше порога в последнем столбце. При ставке 30% этот порог уменьшается, но остаётся выше верхней границы исходного исследования 500 000 долларов за тонну. Поэтому в диапазоне исходного исследования авиация не становится глобально лучшим решением. Порог равенства авиации и моря может быть достигнут раньше, когда железная дорога ещё дешевле обоих вариантов.')
        table(['Ставка; цена тонны','Авиа, долларов','Железная дорога, долларов','Море, долларов','Самый дешёвый маршрут'],
              [[f"{r['wacc']:.0%}; {fmt(r['price_usd_per_t'])}",r['air_log_usd'],r['rail_log_usd'],r['sea_log_usd'],route_label(r['cheapest_route'])] for r in answers['control1_examples']])
        p('При WACC=0 отсутствует выигрыш от сокращения иммобилизации; остаются тариф и CBAM. При положительном WACC порог обратно пропорционален ставке. Таблица показывает, где рост P действительно меняет рейтинг. Равенство пары не гарантирует глобальный минимум, если третий вариант дешевле.')
        heading('6.2. Когда углеродный сбор нивелирует скорость авиации?',2)
        p('Вопрос 2 из задания: сравните железнодорожный экспресс со сроком 18,5 суток и авиационный экспресс со сроком 2,5 суток. При какой стоимости груза экономия капитала начинает перекрывать разницу фрахта? При какой цене европейской углеродной квоты сбор полностью нивелирует выигрыш авиации для груза стоимостью 150 000–300 000 долларов за тонну?')
        p(f"Без CBAM авиа–ж/д сравнивается по разнице фрахта {fmt(answers['air_rail_freight_gap_usd'])} USD. Порог P при WACC=15% равен {fmt(answers['price_air_rail_freight_only_usd_per_t'])} USD/т. С исходным CBAM он повышается до {fmt(answers['price_air_rail_including_cbam_usd_per_t'])} USD/т.")
        p('Расшифровка обозначений: CBAM — механизм трансграничной углеродной корректировки; WACC — средневзвешенная стоимость капитала; P — цена одной тонны; USD — доллар Соединённых Штатов Америки; ж/д — железнодорожный транспорт. При массе 20 тонн и ставке капитала 15% выигрыш авиации в 16 суток даёт экономию 20·P·0,15·16/365. Этот результат сравнивается с надбавкой фрахта, а затем с надбавкой углеродного сбора.')
        table(['Цена тонны, долларов','Экономия капитала, долларов','Надбавка фрахта, долларов','Цена квоты равенства, евро/тонну выбросов'],
              [[r['price_usd_per_t'],r['capital_saving_usd'],r['freight_delta_usd'],r['ets_equality_eur']] for r in metrics['tco']['sensitivity']['ets_thresholds']])
        p('ETS* = Origin + (V·P·WACC·16/365 − ΔC_freight) / [V·EUR_USD·(E_air−E_rail)]. При P=150–300 тыс. USD/т получены отрицательные ETS*, приведённые в разделе 3.4: выигрыш капитала ещё меньше надбавки фрахта. Следовательно, положительного порога «нивелирования выигрыша» в указанных условиях не существует. При повышении P выше порога без CBAM такой положительный порог может возникнуть; при ETS=Origin углеродный ценовой спред равен нулю.')
        p('В последней формуле ETS* — цена углеродной квоты, при которой затраты сравниваются; Origin — цена углерода в стране происхождения; EUR_USD — курс долларов за евро; E_air и E_rail — удельные транспортные выбросы авиации и железной дороги; ΔC_freight — надбавка фрахта. Отрицательная вычисленная цена — только алгебраическое равенство за пределами допустимой области. Она не означает существование реальной отрицательной цены квоты: при заданных 150–300 тысячах долларов за тонну авиация уже проигрывает по фрахту, и положительный сбор увеличивает её отставание.')
        heading('6.3. Физико-химические риски и IoT → ERP',2)
        p('Вопрос 3 из задания: какие параметры сенсорных регистраторов критичны при перевозке пирофорных электронных газов — силана (SiH4) и фосфина (PH3)? Как интеграция этих данных в систему управления ресурсами предприятия (ERP, Enterprise Resource Planning) помогает предотвратить аварийные остановки полупроводниковых чистых комнат? IoT (Internet of Things) означает интернет вещей, то есть сеть подключённых измерительных устройств.')
        table(['Что контролировать','Зачем нужен параметр','Использование сигнала'],[
            ['Температура и скорость её изменения','Выявление перегрева и отклонения условий перевозки','Проверка качества партии; запрет допуска при нарушении установленного регламента'],
            ['Давление и его изменение с учётом температуры','Выявление изменения состояния содержимого; одного давления недостаточно для доказательства утечки','Сопоставление с другими датчиками и направление на проверку герметичности'],
            ['Утечки и герметичность','Обнаружение выхода опасного газа; для силана важен риск воспламенения, для фосфина — токсичность','Локальная защитная реакция и уведомление ответственных; регистрация события в учёте партии'],
            ['Ускорения по трём осям и вибрации','Выявление ударов, способных повредить арматуру или крепления','Осмотр и диагностика до допуска груза в производство'],
            ['Исправность, питание, связь и время измерения','Потеря сигнала не должна трактоваться как отсутствие опасности','Пометка недостоверных или устаревших данных, буферизация и восстановление истории'],
        ])
        p('Для силана и фосфина важны температура и давление с контролем скорости изменения, химически селективное обнаружение утечек, целостность герметизации, трёхосевые ускорения и вибрации, состояние арматуры, питания и связи. Тип датчика, совместимость материалов, рабочий диапазон и калибровка выбираются по конкретному газу и оборудованию. Давление без температурной компенсации не позволяет однозначно отличить нагрев от утечки.')
        p('По паспортам безопасности Airgas (силан SiH4, документ SDS 001073; фосфин PH3, документ SDS 001070) эти газы требуют контроля воспламенения и герметичности; токсичность фосфина делает обнаружение утечек отдельной задачей. SDS (Safety Data Sheet) — паспорт безопасности химической продукции. Эти сведения подтверждают инженерный выбор контролируемых параметров, но численные пороги для силана и фосфина в данной работе не задаются. Учебный коридор −22…−18 °C относится к предоставленному сценарию фтороводорода (HF) и не переносится на другие вещества.')
        p('Предлагаемая интеграция: подписанные сообщения с идентификатором партии (batch_id), временем и качеством измерения → проверка схемы и последовательности → обработчик эпизодов → блокировка выпуска партии в системе управления ресурсами предприятия → уведомление службы качества и инициирование резервного снабжения → подтверждение допуска или списания с журналом решений. Связь с учётом запасов позволяет исключить негодный груз из доступного остатка, заранее заказать замену и скорректировать производственный план до исчерпания запаса чистой комнаты.')
        p('Быстрые аварийные защиты должны работать локально в сертифицированной системе безопасности независимо от связи с системой управления ресурсами предприятия. Сама система предприятия выполняет прослеживаемость, управление запасом и согласование решений. Фильтрация шума не должна скрывать достоверный удар или длительное нарушение. Нужны диагностика датчиков, контроль устаревших данных, резерв питания, локальный буфер и восстановление последовательности после обрыва связи.')
        p('В исходном CSV есть только GPS, температура, давление и три оси ускорения. Датчиков утечки, влажности, кислорода, пломбы или положения клапанов нет. Их применение — инженерное предложение, не результат измерений данной партии. Ни один финансовый статус DPP сам по себе не заменяет оценку промышленной безопасности.')
        heading('7. Проверка, Harness Log и воспроизводимость')
        table(['Набор','Пройдено','Ошибок','Пропущено','Время, с'],[[{'core':'Вычислительные проверки','artifacts':'Проверки готовых файлов'}.get(x['name'],x['name']),x['passed'],x['failed'],x['skipped'],x['duration_seconds']] for x in tests])
        p('Команды и исходные логи pytest сохранены в test_results.json. Точность независимой денежной сверки 10⁻⁶ USD; корней 10⁻⁵ USD; ограничений 10⁻⁵ т/год; сравнения денежного оптимума 0.01 руб.; независимой сферической проверки GPS 0.001 км. Округление применяется при экспорте паспорта и отображении, а metrics.json сохраняет float полной точности.')
        counts=Counter(x['Status'] for x in harness_rows)
        table(['Текущий запуск журнала проверок','Число записей'],[(status_label(k),v) for k,v in sorted(counts.items())])
        p('Независимые методы: Decimal для TCO; полный перебор 4⁵ назначений SSCFLP; 16 наборов открытий + SciPy/HiGHS для Multi-Sourcing; сферическая формула косинусов для GPS; вторичный SHA-256 от файла. Калькуляторы не используют Harness для получения результатов.')
        p('История включает первоначальный RED без реализации, ошибку доступа к PuLP после установки и зависание CBC при threads=1. Исправления: наследование прав в vendor, последовательный режим threads=0. После исправлений тесты и полный конвейер повторяются. История не удаляется при повторном запуске.')
        warnings=[x for x in harness_rows if x['Status'] in ('WARNING','NOT_VERIFIED','FAIL','BLOCKED')]
        table(['Проверка','Статус','Комментарий'],[[x['Test_ID'],x['Status'],x['Comment']] for x in warnings] or [['Нет','PASS','Текущие вычислительные проверки пройдены']])
        p('Графики проверены программно: конечность серий, подписи и их границы, отсутствие обрезания данных, наличие PNG и элементов в DOCX. Отдельный контроль ZIP/XML проверяет целостность, связи изображений, ширину рисунков и отсутствие служебных заполнителей. Статус фактического рендера страниц указан в report_validation.json; если Word недоступен, пагинация не объявляется визуально проверенной.')
        env=metrics['environment']
        p('Окружение: Python '+env['python']+'; '+env['platform']+'; '+env['processor']+'. Библиотеки: '+', '.join(k+' '+v for k,v in env['packages'].items())+'. CBC 2.10.3, параметры запуска и исходный баннер — в run_manifest.json и logs/cbc_version.txt.')
        p('Единый запуск из корня: .\\.venv\\Scripts\\python.exe 4/app/main.py --data 4/data --output 4/app/output --template end_template/Шаблон_отчета_ЭА_краткий_v2.docx. Тесты: .\\.venv\\Scripts\\python.exe -m pytest 4/app/tests -q -p no:cacheprovider. Численные результаты воспроизводимы; времена CBC и метки запуска меняются.')
        heading('8. Итоги и источники')
        for key in ['tco_baseline','multi','dynamic','gps']:p(narratives[key])
        p('Ограничения: модель риска и расширенного CBAM учебная; эмиссионные коэффициенты и цены фиксированы источником; GPS даёт длину ломаной контрольного участка; общая ставка страхования не учитывает различия модальностей. Вероятность 1 после инцидента — требование регламента задания. Влияние запрета авиационной перевозки конкретной формы HF здесь не моделируется, юридическая допустимость не утверждается.')
        for source in [
          '1. Задание_к_практическому_занятию_4_ЭА.pdf, с. 1–10, 4/data.',
          '2. Лекция 7 ЭА слайды.pdf, с. 7–11, 19–23, 28, 4/data.',
          '3. Первичные module1_tco_cbam_input.json; module2_cflp_customers.csv; module2_cflp_facilities.csv; module2_cflp_tariffs.csv; module3_iot_telemetry.csv, 4/data.',
          '4. Промт_Практическое_занятие_4_ЭА.md, 4/task. Матрица трассировки: docs/SOURCE_AUDIT.md.',
          '5. Airgas, Silane SDS 001073: https://www.airgas.com/msds/001073.pdf; Phosphine SDS 001070: https://www.airgas.com/msds/001070.pdf. Дата обращения 25.10.2026. Разделы 2, 7, 10.',
        ]:p(source)
        path=self.output/REPORT_NAME;doc.save(path)
        return path

def validate_docx(path,expected_images=12):
    path=Path(path)
    with zipfile.ZipFile(path) as z:
        bad=z.testzip()
        if bad: raise ValueError('Повреждён ZIP: '+bad)
        for name in z.namelist():
            if name.endswith('.xml') or name.endswith('.rels'): etree.fromstring(z.read(name))
        root=etree.fromstring(z.read('word/document.xml'))
        ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main','wp':'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing','a':'http://schemas.openxmlformats.org/drawingml/2006/main','r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
        text='\n'.join(root.xpath('//w:t/text()',namespaces=ns))
        count=len(root.xpath('//a:blip',namespaces=ns))
        if count!=expected_images: raise ValueError(f'Рисунков {count}, ожидается {expected_images}')
        if '[значение]' in text or '[ВСТАВИТЬ' in text or '[Наименование' in text: raise ValueError('Остались заполнители')
        widths=[int(v) for v in root.xpath('//wp:extent/@cx',namespaces=ns)]
        if any(v>int(Cm(17.1)) for v in widths): raise ValueError('Рисунок шире полосы текста')
        rel=etree.fromstring(z.read('word/_rels/document.xml.rels'))
        rels={x.get('Id'):x.get('Target') for x in rel}
        for rid in root.xpath('//a:blip/@r:embed',namespaces=ns):
            if 'word/'+rels[rid] not in z.namelist(): raise ValueError('Отсутствует встроенное изображение')
    Document(path)
    return dict(status='PASS',zip_crc='PASS',xml='PASS',embedded_images=count,image_width='PASS',opened_python_docx=True,placeholders='ABSENT')
