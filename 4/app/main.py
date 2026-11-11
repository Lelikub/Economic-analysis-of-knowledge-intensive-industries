from pathlib import Path
import sys

APP=Path(__file__).resolve().parent
sys.path.insert(0,str(APP/'vendor'))
if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')

from src.interface import PipelineCLI

if __name__=='__main__':
    raise SystemExit(PipelineCLI().run())
