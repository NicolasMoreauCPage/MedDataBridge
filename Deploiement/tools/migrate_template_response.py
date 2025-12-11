#!/usr/bin/env python3
"""
Script to migrate deprecated TemplateResponse usage to new API.

Old: templates.TemplateResponse("name.html", {"request": request, ...})
New: templates.TemplateResponse(request, "name.html", {...})
"""
import re
import sys
from pathlib import Path
from typing import List, Tuple


def find_template_response_calls(content: str) -> List[Tuple[int, str]]:
    """Find all TemplateResponse calls with their line numbers."""
    lines = content.split('\n')
    calls = []
    
    for i, line in enumerate(lines, 1):
        # Skip if already using new format
        if 'TemplateResponse(request,' in line:
            continue
            
        # Find TemplateResponse calls
        if 'TemplateResponse(' in line and 'templates.TemplateResponse(' in line:
            calls.append((i, line))
    
    return calls


def migrate_simple_case(line: str) -> str:
    """
    Migrate simple case: TemplateResponse("name.html", {"request": request})
    to: TemplateResponse(request, "name.html")
    """
    # Pattern: TemplateResponse("name", {"request": request})
    pattern = r'templates\.TemplateResponse\("([^"]+)",\s*\{"request":\s*request\}\)'
    replacement = r'templates.TemplateResponse(request, "\1")'
    
    if re.search(pattern, line):
        return re.sub(pattern, replacement, line)
    
    return line


def migrate_with_context(line: str) -> str:
    """
    Migrate with context: TemplateResponse("name", {"request": request, "key": value})
    to: TemplateResponse(request, "name", {"key": value})
    """
    # Pattern: TemplateResponse("name", {"request": request, ...})
    # This is more complex, needs multi-line support
    return line


def migrate_file(file_path: Path, dry_run: bool = False) -> int:
    """Migrate a single file. Returns number of changes."""
    content = file_path.read_text()
    original_lines = content.split('\n')
    modified_lines = original_lines.copy()
    changes = 0
    
    calls = find_template_response_calls(content)
    
    if not calls:
        return 0
    
    print(f"\n📝 {file_path}")
    print(f"   Found {len(calls)} deprecated TemplateResponse calls")
    
    # Migrate each line
    for line_num, line in calls:
        original = line
        migrated = migrate_simple_case(line)
        
        if migrated != original:
            modified_lines[line_num - 1] = migrated
            changes += 1
            print(f"   Line {line_num}:")
            print(f"     - {original.strip()}")
            print(f"     + {migrated.strip()}")
    
    if changes > 0 and not dry_run:
        new_content = '\n'.join(modified_lines)
        file_path.write_text(new_content)
        print(f"   ✅ Saved {changes} changes")
    
    return changes


def main():
    """Main migration script."""
    dry_run = '--dry-run' in sys.argv
    
    print("🔧 TemplateResponse Migration Script")
    print("=" * 60)
    
    if dry_run:
        print("⚠️  DRY RUN MODE - No files will be modified")
        print()
    
    # Find all Python files in app/routers
    app_dir = Path(__file__).parent.parent / "app"
    router_files = list(app_dir.rglob("*.py"))
    
    total_changes = 0
    files_modified = 0
    
    for file_path in sorted(router_files):
        changes = migrate_file(file_path, dry_run=dry_run)
        if changes > 0:
            total_changes += changes
            files_modified += 1
    
    print("\n" + "=" * 60)
    print(f"📊 Summary:")
    print(f"   Files scanned: {len(router_files)}")
    print(f"   Files modified: {files_modified}")
    print(f"   Total changes: {total_changes}")
    
    if dry_run and total_changes > 0:
        print("\n💡 Run without --dry-run to apply changes")
    elif total_changes > 0:
        print("\n✅ Migration complete!")
    else:
        print("\n✅ No deprecated usages found!")


if __name__ == "__main__":
    main()
