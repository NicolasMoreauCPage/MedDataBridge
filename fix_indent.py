#!/usr/bin/env python3
"""Fix indentation in transport_inbound.py after removing 'with ctx:' block."""

file_path = "app/services/transport_inbound.py"

with open(file_path, 'r') as f:
    lines = f.readlines()

# Find the line numbers to fix
fixed_lines = []
in_section = False
section_start = 0

for i, line in enumerate(lines, 1):
    # Detect start: "# Phase 1: Validation PAM"
    if "# Phase 1: Validation PAM" in line and not in_section:
        in_section = True
        section_start = i
        # This line should have 8 spaces (2 levels), keep it
        fixed_lines.append(line)
        continue
    
    # Detect end: "except ValueError as ve:" at top level of function
    if in_section and line.strip().startswith("except ValueError as ve:"):
        in_section = False
        fixed_lines.append(line)
        continue
    
    # Fix lines in section: remove 4 spaces from the beginning
    if in_section and line.startswith("            "):  # 12 spaces or more
        # Remove 4 spaces
        fixed_lines.append(line[4:])
    else:
        fixed_lines.append(line)

# Write back
with open(file_path, 'w') as f:
    f.writelines(fixed_lines)

print(f"✅ Fixed indentation in {file_path}")
print(f"   Section from line {section_start} was de-indented by 4 spaces")
