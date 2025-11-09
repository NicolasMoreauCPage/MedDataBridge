#!/usr/bin/env python3
"""
Fix all deprecated TemplateResponse usage in the codebase.

This script converts:
    templates.TemplateResponse(
        "template.html",
        {"request": request, ...}
    )

To:
    templates.TemplateResponse(
        request,
        "template.html",
        {...}  # with "request": request removed from context
    )
"""
import re
from pathlib import Path
from typing import List, Tuple


def fix_template_response_in_file(file_path: Path, dry_run: bool = False) -> int:
    """
    Fix all TemplateResponse calls in a file.
    Returns the number of fixes applied.
    """
    content = file_path.read_text()
    
    # Pattern to match old-style TemplateResponse
    # Match: templates.TemplateResponse(\n    "template", {...})
    # This pattern handles multi-line calls
    pattern = r'''(templates\.TemplateResponse\(\s*\n\s*)("[\w._-]+",)\s*(\{[^}]*"request":\s*request[^}]*\})'''
    
    matches = list(re.finditer(pattern, content, re.MULTILINE | re.DOTALL))
    
    if not matches:
        return 0
    
    # Safe relative path handling
    try:
        rel_path = file_path.relative_to(Path.cwd())
    except ValueError:
        rel_path = file_path
    
    print(f"\n📝 {rel_path}")
    print(f"   Found {len(matches)} deprecated calls")
    
    # Replace in reverse order to preserve positions
    new_content = content
    changes = 0
    
    for match in reversed(matches):
        full_match = match.group(0)
        prefix = match.group(1)  # "templates.TemplateResponse(\n    "
        template_name = match.group(2)  # '"template.html",'
        context_dict = match.group(3)  # '{...}'
        
        # Remove "request": request from context
        # Keep other context items
        new_context = re.sub(r'"request":\s*request,?\s*', '', context_dict)
        new_context = re.sub(r',\s*}', '}', new_context)  # Remove trailing comma
        
        # If context is now empty {}, simplify
        if new_context.strip() in ['{', '{}']:
            new_call = f"{prefix}request,\n        {template_name.rstrip(',')}"
        else:
            # Keep remaining context
            new_call = f"{prefix}request,\n        {template_name}\n        {new_context}"
        
        # Replace in content
        new_content = new_content[:match.start()] + new_call + new_content[match.end():]
        changes += 1
    
    if changes > 0:
        print(f"   ✅ Fixed {changes} calls")
        
        if not dry_run:
            file_path.write_text(new_content)
            print(f"   💾 Saved changes")
    
    return changes


def main():
    import sys
    
    dry_run = '--dry-run' in sys.argv or '-n' in sys.argv
    
    print("🔧 TemplateResponse Deprecation Fix")
    print("=" * 70)
    
    if dry_run:
        print("⚠️  DRY RUN - No files will be modified\n")
    
    # Find all Python files in app/
    app_dir = Path("app")
    if not app_dir.exists():
        print("❌ Error: app/ directory not found")
        print("   Run this script from the project root")
        return 1
    
    python_files = list(app_dir.rglob("*.py"))
    
    total_changes = 0
    files_modified = 0
    
    for file_path in sorted(python_files):
        changes = fix_template_response_in_file(file_path, dry_run=dry_run)
        if changes > 0:
            total_changes += changes
            files_modified += 1
    
    print("\n" + "=" * 70)
    print(f"📊 Summary:")
    print(f"   Files scanned: {len(python_files)}")
    print(f"   Files modified: {files_modified}")
    print(f"   Total fixes: {total_changes}")
    
    if dry_run and total_changes > 0:
        print("\n💡 Run without --dry-run to apply changes:")
        print(f"   python {sys.argv[0]}")
    elif total_changes > 0:
        print("\n✅ All deprecations fixed!")
        print("\n⚠️  Remember to run tests to verify changes:")
        print("   pytest tests/")
    else:
        print("\n✅ No deprecated usage found!")
    
    return 0


if __name__ == "__main__":
    exit(main())
