#!/usr/bin/env python3
"""Add session.commit() before all 'return ack' statements that follow 'log.ack_payload = ack'."""

file_path = "app/services/transport_inbound.py"

with open(file_path, 'r') as f:
    lines = f.readlines()

fixed_lines = []
i = 0
modifications = 0

while i < len(lines):
    line = lines[i]
    fixed_lines.append(line)
    
    # Check if this line is "log.ack_payload = ack"
    if "log.ack_payload = ack" in line and not line.strip().startswith("#"):
        # Check if next line is "return ack"
        if i + 1 < len(lines) and "return ack" in lines[i + 1]:
            # Get indentation of return statement
            indent = len(lines[i + 1]) - len(lines[i + 1].lstrip())
            indent_str = " " * indent
            
            # Check if commit is not already there
            commit_line = f"{indent_str}if should_commit:\n"
            commit_line2 = f"{indent_str}    session.commit()\n"
            
            # Add the commit before return
            fixed_lines.append(commit_line)
            fixed_lines.append(commit_line2)
            modifications += 1
    
    i += 1

# Write back
with open(file_path, 'w') as f:
    f.writelines(fixed_lines)

print(f"✅ Added {modifications} commit statements before 'return ack'")
