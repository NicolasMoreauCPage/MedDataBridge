#!/usr/bin/env python3
"""Test validation of message #5544 with corrected XTN parsing."""
from app.services.pam_validation import validate_pam

# Read message
with open("/tmp/test_msg_5544.hl7", "r") as f:
    message = f.read()

print("🧪 Testing validation of message #5544 with XTN fix\n")
print(f"Message (first 200 chars): {message[:200]}...\n")

# Validate
result = validate_pam(message, direction="in", profile="IHE_PAM_FR")

print(f"Validation Level: {result.level}")
print(f"Total Issues: {len(result.issues)}\n")

# Show issues related to XTN
xtn_issues = [i for i in result.issues if "XTN" in i.code or "PID13" in i.code]
if xtn_issues:
    print(f"XTN-related issues: {len(xtn_issues)}")
    for issue in xtn_issues:
        print(f"  [{issue.severity}] {issue.code}: {issue.message}")
else:
    print("✅ No XTN-related issues!")

print(f"\nAll issues ({len(result.issues)}):")
for issue in result.issues:
    print(f"  [{issue.severity}] {issue.code}: {issue.message}")
