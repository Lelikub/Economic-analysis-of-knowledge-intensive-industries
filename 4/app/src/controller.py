from .orchestrator import PipelineOrchestrator

class SprintController:
    def execute(self,data_dir,output,template):
        return PipelineOrchestrator(data_dir,output,template).run()
