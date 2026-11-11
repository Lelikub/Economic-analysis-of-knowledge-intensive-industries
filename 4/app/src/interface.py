import argparse
from pathlib import Path
from .controller import SprintController

class PipelineCLI:
    def __init__(self,controller=None):self.controller=controller or SprintController()
    def run(self):
        root=Path(__file__).resolve().parents[3]
        parser=argparse.ArgumentParser(description='Практическая работа 4: TCO, CFLP, IoT и Word')
        parser.add_argument('--data',type=Path,default=root/'4/data')
        parser.add_argument('--output',type=Path,default=root/'4/app/output')
        parser.add_argument('--template',type=Path,default=root/'end_template/Шаблон_отчета_ЭА_краткий_v2.docx')
        args=parser.parse_args()
        self.controller.execute(args.data,args.output,args.template)
        return 0
