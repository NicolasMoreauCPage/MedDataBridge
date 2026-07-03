# BUG REPORT - IntegraSanté

**Generated:** 2026-03-27T11:08:59.630576
**Total Bugs:** 1
**Test Environment:** http://localhost:8000

## Bug #1: Cannot create patient

- **Severity:** CRITICAL
- **Category:** Patient Management
- **Endpoint:** `POST /api/patients`
- **Steps to Reproduce:**
  ```
  POST /api/patients with valid patient data
  ```
- **Expected:** HTTP 200/201 with patient object
- **Actual:** HTTP 422: {"detail":[{"type":"missing","loc":["body","family"],"msg":"Field required","input":{"ej_id":1,"name":"BugTest Patient","date_birth":"1990-01-01","sex

