from dataclasses import asdict,is_dataclass
from datetime import datetime
from pathlib import Path
import json
import pandas as pd
import numpy as np

def plain(value):
    if is_dataclass(value): return plain(asdict(value))
    if isinstance(value,pd.DataFrame): return plain(value.to_dict(orient='records'))
    if isinstance(value,dict): return {str(k):plain(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)): return [plain(v) for v in value]
    if isinstance(value,(Path,datetime)): return str(value)
    if isinstance(value,np.generic): return value.item()
    return value

def write_json(path,value):
    Path(path).write_text(json.dumps(plain(value),ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
