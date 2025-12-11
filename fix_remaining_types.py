"""Fix remaining Python 3.8 type hint compatibility issues."""
import re
from pathlib import Path

files = [
    'app/services/scenario_realistic_timeplan.py',
    'app/services/scenario_timeplan.py',
    'app/services/scenario_loader.py',
    'app/services/fhir_resources.py',
    'app/services/hl7_parser.py',
    'app/routers/dossiers.py',
    'app/routers/ght/helpers.py',
    'app/routers/ght/structure.py',
]

for f in files:
    p = Path(f)
    if not p.exists():
        print(f"Not found: {f}")
        continue
    content = p.read_text(encoding='utf-8')
    original = content
    
    # Replace type hints
    content = re.sub(r'\blist\[', 'List[', content)
    content = re.sub(r'\bdict\[', 'Dict[', content)
    content = re.sub(r'\btuple\[', 'Tuple[', content)
    content = re.sub(r'\bset\[', 'Set[', content)
    
    if content != original:
        # Add imports if needed
        m = re.search(r'^from typing import (.+)$', content, re.MULTILINE)
        if m:
            imports = set(i.strip() for i in m.group(1).split(','))
            needed = []
            if 'List[' in content and 'List' not in imports:
                needed.append('List')
            if 'Dict[' in content and 'Dict' not in imports:
                needed.append('Dict')
            if 'Tuple[' in content and 'Tuple' not in imports:
                needed.append('Tuple')
            if 'Set[' in content and 'Set' not in imports:
                needed.append('Set')
            if needed:
                imports.update(needed)
                new_line = f"from typing import {', '.join(sorted(imports))}"
                content = content.replace(m.group(0), new_line)
        p.write_text(content, encoding='utf-8')
        print(f'Fixed: {f}')
    else:
        print(f"No changes: {f}")
