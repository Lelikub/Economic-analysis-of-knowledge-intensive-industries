import hashlib
import importlib.metadata
import platform
import subprocess
from pathlib import Path
from .loaders import InputLoader

def sha256(path):
    with Path(path).open('rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()

def environment():
    packages={k:importlib.metadata.version(k) for k in ['numpy','pandas','matplotlib','python-docx','pytest','pulp','scipy','Pillow','pypdf']}
    return dict(python=platform.python_version(),platform=platform.platform(),machine=platform.machine(),processor=platform.processor(),packages=packages,
                cbc_settings=dict(threads=0,execution='serial, CBC threading disabled',time_limit_seconds=60,gap_relative=0,random_seed=1,integer_tolerance=1e-9,primal_tolerance=1e-9),
                earth_radius_km=6371.0088,gps_max_speed_kmh=200,telemetry_timezone='не задана источником; время без преобразования')

def audit_sources(data_dir,output):
    files={p.name:dict(path=str(p.resolve()),sha256=sha256(p),bytes=p.stat().st_size) for p in Path(data_dir).iterdir() if p.is_file()}
    archive=Path(data_dir)/'logistics_hightech_data.rar'
    seven=Path('C:/Program Files/7-Zip/7z.exe')
    comparisons=[]
    if archive.exists() and seven.exists():
        for name in InputLoader.FILENAMES:
            proc=subprocess.run([str(seven),'x','-so',str(archive),'logistics_hightech_data/'+name],capture_output=True)
            digest=hashlib.sha256(proc.stdout).hexdigest()
            comparisons.append(dict(member=name,sha256_archive=digest,sha256_primary=files[name]['sha256'],equal=proc.returncode==0 and digest==files[name]['sha256']))
    return files,comparisons
