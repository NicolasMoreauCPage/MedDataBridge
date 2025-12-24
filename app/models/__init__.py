"""Compatibility package shim for app.models.

This project keeps a module file `app/models.py` alongside a folder
`app/models/`. Some tests and scripts do `from app.models import X` and
expect the module definitions from `app/models.py`. To preserve that
behaviour while keeping the `app/models/` package directory, this shim
loads the source file `app/models.py` under a private name and re-exports
its public symbols into the package namespace.

This avoids circular imports that would occur if we tried `from app import
models` directly.
"""

from __future__ import annotations

import sys
from pathlib import Path
from importlib.util import spec_from_file_location, module_from_spec

# Locate the real module file (one level up from this package dir)
module_file = Path(__file__).parent.parent / "models.py"
if module_file.exists():
	spec = spec_from_file_location("app._models_impl", str(module_file))
	mod = module_from_spec(spec)
	# Register under a private name to allow other imports if needed
	sys.modules[spec.name] = mod
	spec.loader.exec_module(mod)  # type: ignore

	# Re-export public attributes from the loaded module
	for name in dir(mod):
		if not name.startswith("_"):
			globals()[name] = getattr(mod, name)

	__all__ = [n for n in dir(mod) if not n.startswith("_")]
else:
	# Fallback: empty package
	__all__ = []
__all__ = []

