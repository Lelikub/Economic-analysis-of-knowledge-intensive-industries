"""Short-lived Microsoft Excel COM worker used by the Python pipeline."""

from __future__ import annotations

import logging
from pathlib import Path
import sys


def recalculate(path: Path) -> int:
    """Recalculate and save one workbook; return a process exit code."""
    import win32com.client

    excel = None
    workbook = None
    try:
        excel = win32com.client.DispatchEx("Excel.Application")
        excel.Visible = False
        excel.DisplayAlerts = False
        workbook = excel.Workbooks.Open(str(path.resolve()))
        excel.CalculateFullRebuild()
        workbook.Save()
        workbook.Close(SaveChanges=True)
        workbook = None
        return 0
    except Exception:
        logging.exception("Excel COM recalculation failed")
        return 1
    finally:
        if workbook is not None:
            try:
                workbook.Close(SaveChanges=False)
            except Exception:
                logging.exception("Excel COM workbook cleanup failed")
        if excel is not None:
            try:
                excel.Quit()
            except Exception:
                logging.exception("Excel COM application cleanup failed")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        logging.error("Usage: excel_worker.py WORKBOOK_PATH")
        raise SystemExit(2)
    raise SystemExit(recalculate(Path(sys.argv[1])))
