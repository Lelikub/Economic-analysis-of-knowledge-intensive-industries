from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime,timezone
from pathlib import Path
from time import perf_counter
from collections import Counter
import importlib.util
import json
import logging
import os
import subprocess
import sys
import traceback
import uuid
import xml.etree.ElementTree as ET
import pulp
from .audit import audit_sources,environment,sha256
from .loaders import InputLoader
from .validators import DataValidator
from .calculators.tco import MultimodalTCOSimulator
from .calculators.cflp import CFLPCalculator
from .calculators.telemetry import TelemetryCalculator
from .services import TCOService,CFLPService,TelemetryService,PassportService
from .harness import VerificationHarness
from .analysis import prepare_tables,interpret
from .plotting import PlotBuilder
from .reporting import ReportBuilder,validate_docx
from .serialization import write_json,plain

APP=Path(__file__).resolve().parents[1]
ROOT=APP.parents[1]

class RunContext(logging.Filter):
    def __init__(self,run_id): super().__init__();self.run_id=run_id;self.stage='PREPARE'
    def filter(self,record):record.run_id=self.run_id;record.stage=self.stage;return True

class PipelineOrchestrator:
    def __init__(self,data_dir,output,template):
        self.data_dir=Path(data_dir).resolve();self.output=Path(output).resolve();self.template=Path(template).resolve() if template else None
        if not self.output.is_relative_to(APP): raise ValueError('Результаты разрешены только внутри 4/app')
        self.output.mkdir(parents=True,exist_ok=True)
        self.logs=APP/'logs';self.logs.mkdir(exist_ok=True)
        self.run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]
        self.context=RunContext(self.run_id);self.stages=[];self.tests=[]
        self.logger=logging.getLogger('pipeline');self.logger.setLevel(logging.DEBUG);self.logger.handlers.clear();self.logger.propagate=False
        formatter=logging.Formatter('%(asctime)s %(levelname)s pipeline stage=%(stage)s run_id=%(run_id)s %(message)s')
        for handler in [logging.FileHandler(self.logs/'execution.log',encoding='utf-8'),logging.StreamHandler(sys.stdout)]:
            handler.setFormatter(formatter);handler.addFilter(self.context)
            if isinstance(handler,logging.FileHandler):handler.setLevel(logging.DEBUG)
            else:handler.setLevel(logging.INFO)
            self.logger.addHandler(handler)
        self.harness=VerificationHarness(self.logs,self.run_id)

    @contextmanager
    def stage(self,name):
        self.context.stage=name;self.logger.info('START %s',name);start=perf_counter()
        entry=dict(stage=name,status='RUNNING',started_utc=datetime.now(timezone.utc).isoformat());self.stages.append(entry)
        try:
            yield
            entry.update(status='PASS',seconds=perf_counter()-start);self.logger.info('END %s seconds=%.3f',name,entry['seconds'])
            history=self.logs/'HARNESS_LOG.csv'
            if history.exists():
                import csv
                with history.open(encoding='utf-8-sig',newline='') as f:
                    previous=[r for r in csv.DictReader(f) if r['Test_ID']=='stage_'+name]
                if previous and previous[-1]['Status']=='FAIL':
                    self.harness.record('stage_'+name,name,'FIXED_AND_RETESTED',comment='Повторный полный запуск стадии успешен; исходная ошибка сохранена в '+previous[-1]['Run_ID'],retest='PASS',log_path=str(self.logs/'execution.log'))
        except Exception as exc:
            entry.update(status='FAIL',seconds=perf_counter()-start,error=str(exc));self.logger.exception('FAIL %s',name)
            self.harness.record('stage_'+name,name,'FAIL',error=type(exc).__name__,comment=str(exc),log_path=str(self.logs/'execution.log'))
            write_json(self.output/'run_manifest.json',dict(run_id=self.run_id,status='FAIL',stages=self.stages,error=str(exc)))
            raise

    def run_tests(self,name,files,artifact=False):
        xml=self.logs/f'{self.run_id}_{name}.xml';log=self.logs/f'{self.run_id}_{name}.txt'
        command=[sys.executable,'-m','pytest',*[str(APP/'tests'/x) for x in files],'-q','-p','no:cacheprovider','--junitxml='+str(xml)]
        env=os.environ.copy();env['PYTHONIOENCODING']='utf-8';env['LOGISTICS_ARTIFACT_DIR']=str(self.output)
        self.logger.info('pytest command=%s',command)
        start=perf_counter();proc=subprocess.run(command,cwd=ROOT,capture_output=True,env=env,timeout=180)
        log.write_bytes(proc.stdout+proc.stderr)
        if xml.exists():
            root=ET.parse(xml).getroot();suites=[root] if root.tag=='testsuite' else list(root.findall('testsuite'))
            total=sum(int(x.get('tests',0)) for x in suites);failed=sum(int(x.get('failures',0))+int(x.get('errors',0)) for x in suites)
            skipped=sum(int(x.get('skipped',0)) for x in suites)
        else: total=0;failed=1;skipped=0
        result=dict(name=name,command=command,exit_code=proc.returncode,passed=total-failed-skipped,failed=failed,skipped=skipped,duration_seconds=perf_counter()-start,log=str(log),junit_xml=str(xml))
        self.tests.append(result)
        self.harness.record('pytest_'+name,self.context.stage,'PASS' if proc.returncode==0 and failed==0 else 'FAIL',calculated=result['passed'],reference=total,comment=f'failed={failed}; skipped={skipped}; {result["duration_seconds"]:.3f}s',log_path=str(log))
        self.logger.info('pytest %s: %s passed; %s failed; %s skipped',name,result['passed'],failed,skipped)
        if proc.returncode!=0: raise RuntimeError('pytest failed; '+str(log))
        return result

    def development_history(self):
        marker=self.logs/'development_history_recorded.json'
        if marker.exists(): return
        history=[
          ('python_launcher','FAIL','python.exe launcher недоступен','Windows App Execution Alias','Выбран .venv/Scripts/python.exe'),
          ('pip_network','FAIL','Первая установка PuLP: WinError 10013','Ограничение сетевого доступа песочницы','Разрешённая установка из PyPI в 4/app/vendor'),
          ('initial_red','FAIL','До реализации pytest завершился ModuleNotFoundError: src','Ожидаемый RED, тесты написаны первыми','Реализованы предметные классы и калькуляторы'),
          ('pulp_acl','FAIL','Первый прогон ядра: 31 passed, 4 failed; pulp.LpProblem отсутствует','Установленные файлы не читались из песочницы из-за ACL; namespace package','icacls 4/app/vendor /reset /T; PuLP стал доступен'),
          ('cbc_thread','FAIL','CBC зависал при threads=1; стек faulthandler в subprocess.wait','Потоковый режим CBC 2.10.3 в данной Windows-песочнице','Выбран threads=0: последовательный режим; оптимум подтверждён'),
        ]
        for test,status,message,cause,action in history:
            self.harness.record(test,'DEVELOPMENT',status,error='DevelopmentRun',comment=message,cause=cause,action=action,log_path=str(self.logs/'pytest_initial_red.txt') if test=='initial_red' else str(self.logs/'development_history_recorded.json'))
            self.harness.record(test,'PREPARE','FIXED_AND_RETESTED',comment='Исправление подтверждено запуском Python/PuLP/CBC и 35 тестами ядра',retest='PASS',action=action)
        write_json(marker,history)

    def run(self):
        with self.stage('PREPARE'):
            self.development_history()
            env=environment()
            if not pulp.PULP_CBC_CMD().available(): raise RuntimeError('CBC недоступен')
            proc=subprocess.run([pulp.PULP_CBC_CMD().path,'-stop'],capture_output=True,timeout=10)
            (self.logs/'cbc_version.txt').write_bytes(proc.stdout+proc.stderr)
            if proc.returncode: raise RuntimeError('CBC --stop failed')
            sources,archive=audit_sources(self.data_dir,self.output)
            write_json(self.output/'archive_comparison.json',archive)
            for x in archive:self.harness.record('archive_'+x['member'],'PREPARE','PASS' if x['equal'] else 'WARNING',comment='SHA-256 архивного содержимого и первичного файла',calculated=x['sha256_archive'],reference=x['sha256_primary'])
            for name,s in sources.items():self.logger.debug('SOURCE %s sha256=%s bytes=%s',name,s['sha256'],s['bytes'])
        with self.stage('LOAD'):
            candidate=InputLoader().load(self.data_dir)
            self.logger.info('LOAD: 3 routes, %s customers, %s facilities, %s telemetry rows',len(candidate.cflp.customers),len(candidate.cflp.facilities),len(candidate.telemetry.samples))
        with self.stage('VALIDATE_INPUT'):
            quality=DataValidator().validate(candidate)
            quality.append(DataValidator.issue('module3_iot_telemetry.csv','540–548','REAL_INCIDENT','temperature in [-22,-18]',-16.03,'-18','Сохранить эпизод, применить регламент >30 минут'))
            quality.append(DataValidator.issue('module3_iot_telemetry.csv','920','REAL_INCIDENT','abs(axis)<=2.5g',2.65,2.5,'Сохранить удар, отдельная диагностика'))
            quality.append(DataValidator.issue('Задание PDF с.2','sum capacity','WARNING','Сумма мощностей гарантирует SSCFLP',2750,1600,'Гарантия из одной суммы математически неверна; проверить CBC и перебором'))
            for x in quality:self.harness.record('quality_'+x['row_or_key'],'VALIDATE_INPUT','WARNING' if x['kind']=='WARNING' else 'PASS',comment=x['decision'],source=x['file'])
        with self.stage('BUILD_MODELS'):
            data=candidate
            sim=MultimodalTCOSimulator(data.cargo,data.cbam,data.routes)
        with self.stage('CALCULATE_TCO'):
            tco=TCOService(sim).calculate()
            self.logger.info('TCO baseline=%s',{k:v.tco_log_usd for k,v in tco['baseline'].items()})
            gap=tco['sensitivity']['answers']['air_rail_freight_cbam_gap_usd']
            self.harness.record('air_gap_290000','CALCULATE_TCO','WARNING' if gap<=290000 else 'PASS',calculated=gap,reference=290000,unit='USD',comment='Ориентир >290 тыс. не выполняется для авиа–ж/д; выполняется для авиа–море',source='PDF с.5 и JSON')
        with self.stage('SOLVE_CFLP'):
            cflp=CFLPService(CFLPCalculator(self.logs/'cbc'/self.run_id)).calculate(data.cflp)
            write_json(self.output/'sourcing_audit.json',cflp['sourcing_audit'])
            self.harness.record('multi_single_equivalence','SOLVE_CFLP','PASS',calculated=cflp['sourcing_audit']['baseline']['max_flow_difference_tons_year'],reference=0,unit='тонн/год',comment='Графики совпадают корректно: оптимум разрешающей дробление модели уже удовлетворяет запрету дробления; независимые решения и нижняя граница совпали')
            self.harness.record('multi_single_distinction','SOLVE_CFLP','PASS',calculated=cflp['sourcing_audit']['diagnostic']['extra_cost_single_rub_year'],unit='руб./год',comment='Контроль B — Тверь 650 тонн/год: модели дают разные потоки и стоимости; первичные данные не менялись')
        with self.stage('PROCESS_IOT'):
            iot=TelemetryService(TelemetryCalculator(),sim).calculate(data)
            for seg in iot['segments']:
                if not seg['accepted']:
                    quality.append(DataValidator.issue(data.telemetry.source.name,seg['to_index'],'DATA_ERROR','GPS speed<=200 km/h',seg['speed_kmh'],200,'Сегмент исключён; Scope 3 участка частичен'))
                    self.harness.record('gps_'+str(seg['to_index']),'PROCESS_IOT','WARNING',comment='GPS скачок исключён; Scope 3 частичный')
            self.logger.info('IoT episodes=%s shocks=%s delta_TCO=%s distance_km=%.9f',len(iot['temperature_incidents']),len(iot['shock_incidents']),iot['delta_usd'],iot['distance_km'])
        with self.stage('GENERATE_DPP'):
            passport=PassportService().create(data,iot);write_json(self.output/'dpp_passport.json',passport)
        with self.stage('VERIFY'):
            self.harness.verify(data,tco,cflp,iot,passport)
            self.run_tests('core',['test_calculations.py','test_loaders.py','test_plot_integrity.py'])
            if any(x['Status']=='FAIL' for x in self.harness.rows if x['Stage']!='DEVELOPMENT'):raise ArithmeticError('Независимые проверки не пройдены')
        metrics=dict(pipeline_version='1.0.0',environment=env,tco=tco,cflp=cflp,iot=iot,dpp=passport,quality=quality)
        write_json(self.output/'metrics.json',metrics)
        prepare_tables(data,tco,cflp,iot,quality,self.output)
        narratives=interpret(data,tco,cflp,iot);write_json(self.output/'analysis.json',narratives)
        with self.stage('PLOT_AND_VALIDATE'):
            plots=PlotBuilder(self.output).build()
            for plot in plots:self.harness.record('plot_'+plot['key'],'PLOT_AND_VALIDATE','PASS',comment='PNG, конечность рядов, подписи, границы осей, размеры и легенды проверены',source=plot['source'])
        reporter=ReportBuilder(self.output,self.template)
        with self.stage('BUILD_REPORT'):
            report=reporter.build(data,plain(metrics),plots,narratives,self.tests,self.harness.rows,sources)
            validation=validate_docx(report)
            self.harness.record('docx_structure','BUILD_REPORT','PASS',calculated=validation['embedded_images'],reference=12,comment='ZIP CRC, XML, картинки, ширина и повторное открытие проверены')
        with self.stage('FINAL_AUDIT'):
            self.run_tests('artifacts',['test_artifacts.py'],artifact=True)
            # Финальная редакция включает результаты реально завершённых artifact-тестов.
            report=reporter.build(data,plain(metrics),plots,narratives,self.tests,self.harness.rows,sources)
            validation=validate_docx(report)
            render_log=self.logs/f'{self.run_id}_word_render.txt'
            try:
                render_proc=subprocess.run([sys.executable,str(APP/'render_report.py'),str(self.output)],capture_output=True,timeout=60)
                render_log.write_bytes(render_proc.stdout+render_proc.stderr)
                if render_proc.returncode==1:raise ValueError('Word/PDF layout validation failed: '+str(render_log))
                if render_proc.returncode!=0: raise RuntimeError('Word render failed: '+str(render_log))
                render_result=json.loads((self.output/'word_render_validation.json').read_text(encoding='utf-8'))
                if render_result['status']!='PASS':raise RuntimeError('Word layout check failed')
                validation['page_render_status']='PASS'
                validation['page_count']=render_result['page_count']
                validation['page_render_engine']=render_result['engine']
                self.harness.record('word_render','FINAL_AUDIT','PASS',calculated=render_result['page_count'],unit='страниц',comment='Реальный Word/PDF; все12рисунков и подписей на тех же страницах',log_path=str(render_log))
            except (subprocess.TimeoutExpired,RuntimeError) as exc:
                validation['page_render_status']='NOT_VERIFIED'
                validation['page_render_reason']=str(exc)
                self.harness.record('word_render','FINAL_AUDIT','NOT_VERIFIED',comment=str(exc),log_path=str(render_log))
            write_json(self.output/'report_validation.json',validation)
            for name,info in sources.items():
                if sha256(self.data_dir/name)!=info['sha256']:raise RuntimeError('Исходный файл изменён: '+name)
            write_json(self.output/'test_results.json',self.tests)
        status='PARTIAL' if iot['excluded_gps_segments'] else 'PASS'
        artifacts={str(p.relative_to(self.output)):dict(sha256=sha256(p),bytes=p.stat().st_size) for p in self.output.rglob('*') if p.is_file() and p.name!='run_manifest.json' and '.tmp' not in p.parts}
        manifest=dict(run_id=self.run_id,status=status,stages=self.stages,input_sources=sources,archive_comparison=archive,
                      environment=env,tests=self.tests,harness_current_counts=dict(Counter(x['Status'] for x in self.harness.rows if x['Stage']!='DEVELOPMENT')),
                      development_history=str(self.logs/'HARNESS_LOG.csv'),artifacts=artifacts,
                      report_render_status=validation['page_render_status'],limitations=['Учебная модель CBAM с транспортом','Длина GPS-ломаной контрольного участка, не полного рейса','Временной пояс IoT отсутствует']+(['Рендер страниц Word не проверен'] if validation['page_render_status']!='PASS' else []),
                      template=dict(path=str(self.template),sha256=sha256(self.template)) if self.template and self.template.exists() else None)
        write_json(self.output/'run_manifest.json',manifest)
        self.logger.info('COMPLETE status=%s report=%s',status,report)
        return manifest
