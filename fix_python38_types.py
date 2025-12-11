"""Fix Python 3.8 type hint compatibility issues.

Python 3.8 requires importing List, Dict, Tuple, Set from typing module.
Python 3.9+ allows using list[], dict[], tuple[], set[] directly.
"""

import re
from pathlib import Path

def fix_file(file_path: Path) -> bool:
    """Fix type hints in a single file. Returns True if changes were made."""
    try:
        content = file_path.read_text(encoding='utf-8')
        original_content = content
        
        # Check if we need to add imports
        needs_list = bool(re.search(r'-> list\[|: list\[|\| list\[', content))
        needs_dict = bool(re.search(r'-> dict\[|: dict\[|\| dict\[', content))
        needs_tuple = bool(re.search(r'-> tuple\[|: tuple\[|\| tuple\[', content))
        needs_set = bool(re.search(r'-> set\[|: set\[|\| set\[', content))
        
        if not (needs_list or needs_dict or needs_tuple or needs_set):
            return False
        
        # Replace lowercase with capitalized versions
        if needs_list:
            content = re.sub(r'\blist\[', 'List[', content)
        if needs_dict:
            content = re.sub(r'\bdict\[', 'Dict[', content)
        if needs_tuple:
            content = re.sub(r'\btuple\[', 'Tuple[', content)
        if needs_set:
            content = re.sub(r'\bset\[', 'Set[', content)
        
        # Find the import section and add needed imports
        import_match = re.search(r'^from typing import (.+)$', content, re.MULTILINE)
        if import_match:
            existing_imports = import_match.group(1)
            new_imports = []
            
            if needs_list and 'List' not in existing_imports:
                new_imports.append('List')
            if needs_dict and 'Dict' not in existing_imports:
                new_imports.append('Dict')
            if needs_tuple and 'Tuple' not in existing_imports:
                new_imports.append('Tuple')
            if needs_set and 'Set' not in existing_imports:
                new_imports.append('Set')
            
            if new_imports:
                # Parse existing imports
                import_parts = [i.strip() for i in existing_imports.split(',')]
                import_parts.extend(new_imports)
                import_parts = sorted(set(import_parts))
                new_import_line = f"from typing import {', '.join(import_parts)}"
                content = content.replace(import_match.group(0), new_import_line)
        else:
            # No typing import exists, add one
            import_names = []
            if needs_list:
                import_names.append('List')
            if needs_dict:
                import_names.append('Dict')
            if needs_tuple:
                import_names.append('Tuple')
            if needs_set:
                import_names.append('Set')
            
            if import_names:
                # Find the first import statement
                first_import = re.search(r'^import |^from ', content, re.MULTILINE)
                if first_import:
                    new_import = f"from typing import {', '.join(sorted(import_names))}\n"
                    content = content[:first_import.start()] + new_import + content[first_import.start():]
                else:
                    # Add at the beginning after docstring if present
                    if content.startswith('"""') or content.startswith("'''"):
                        end_docstring = content.find('"""', 3)
                        if end_docstring == -1:
                            end_docstring = content.find("'''", 3)
                        if end_docstring != -1:
                            new_import = f"\n\nfrom typing import {', '.join(sorted(import_names))}\n"
                            content = content[:end_docstring+3] + new_import + content[end_docstring+3:]
        
        if content != original_content:
            file_path.write_text(content, encoding='utf-8')
            print(f"✅ Fixed: {file_path}")
            return True
        return False
    except Exception as e:
        print(f"❌ Error fixing {file_path}: {e}")
        return False

def main():
    """Fix all Python files in app/ directory."""
    files_to_fix = [
        "app/services/mllp_manager.py",
        "app/services/identifier_namespace_classifier.py",
        "app/services/scenario_status_service.py",
        "app/services/scenario_dashboard.py",
        "app/services/scenario_capture.py",
        "app/services/scenario_runner.py",
        "app/services/scenario_realistic_timeplan.py",
        "app/services/scenario_timeplan.py",
        "app/services/scenario_loader.py",
        "app/services/fhir_producer.py",
        "app/services/fhir_bundle.py",
        "app/services/fhir_resources.py",
        "app/services/transport_pdq.py",
        "app/services/pam_parser.py",
        "app/services/hl7_parser.py",
        "app/runtime/runners.py",
        "app/runners.py",
        "app/routers/dossiers.py",
        "app/routers/mllp.py",
        "app/routers/ght/helpers.py",
        "app/routers/ght/structure.py",
        "app/models_hl7.py",
    ]
    
    base_path = Path(__file__).parent
    fixed_count = 0
    
    for file_rel in files_to_fix:
        file_path = base_path / file_rel
        if file_path.exists():
            if fix_file(file_path):
                fixed_count += 1
        else:
            print(f"⚠️  Not found: {file_path}")
    
    print(f"\n✅ Fixed {fixed_count} files")

if __name__ == "__main__":
    main()
