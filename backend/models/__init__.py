"""
Re-export all models from the original monolithic models.py
so that both `from .. import models` and `from ..models import documentary`
work correctly when this directory is treated as the `models` package.

The original `models.py` lives at `backend/models.py` (sibling of this directory).
"""

import importlib.util
import sys
from pathlib import Path

_models_py = Path(__file__).parent.parent / "models.py"
_spec = importlib.util.spec_from_file_location("_movabel_flat_models", _models_py)
_flat = importlib.util.module_from_spec(_spec)
sys.modules["_movabel_flat_models"] = _flat
_spec.loader.exec_module(_flat)

# Re-export every public name from models.py into this package namespace
for _name in dir(_flat):
    if not _name.startswith("_"):
        globals()[_name] = getattr(_flat, _name)
