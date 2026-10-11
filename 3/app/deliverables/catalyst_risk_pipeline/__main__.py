import argparse
from pathlib import Path

from .orchestrator import PipelineOrchestrator


def main():
    base = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Variant B catalyst risk pipeline")
    parser.add_argument("--data", type=Path, default=base.parent / "data")
    parser.add_argument("--template", type=Path, default=base.parents[1] / "end_template/Шаблон_отчета_ЭА_краткий_v2.docx")
    parser.add_argument("--output", type=Path, default=base / "deliverables")
    parser.add_argument("--n", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=314159)
    args = parser.parse_args()
    output = PipelineOrchestrator(args.data, args.template, args.output, args.n, args.seed).run()
    print(output / "run_manifest.json")


if __name__ == "__main__":
    main()
