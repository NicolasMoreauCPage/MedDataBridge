# Quick Test Guide: Mouvement Form Enhancements

## Prerequisites

- FastAPI server running on `http://127.0.0.1:8000`
- SQLite database with structure data (UF, UH, Chambre, Lit)
- Sample movement reasons in vocabulary

## Step-by-Step Testing

### 1. Test AJAX Endpoints Directly

Use curl or Postman to test the three new endpoints:

```bash
# Get Chambres for UniteHebergement ID 1
curl -s "http://127.0.0.1:8000/api/mouvements/chambres/1" | python3 -m json.tool

# Get Lits for Chambre ID 1
curl -s "http://127.0.0.1:8000/api/mouvements/lits/1" | python3 -m json.tool

# Get Reasons for Movement Type A01
curl -s "http://127.0.0.1:8000/api/mouvements/reasons/A01" | python3 -m json.tool
```

**Expected Response Format:**
```json
{
  "success": true,
  "options": [
    {"value": "1", "label": "Chambre A101 (CH-A101)"},
    {"value": "2", "label": "Chambre A102 (CH-A102)"}
  ]
}
```

### 2. Test Form with Browser

#### Open the Form
1. Navigate to `http://127.0.0.1:8000/mouvements/new`
2. If redirected to admin, authenticate first
3. Form should load with all fields visible

#### Test Cascading Select Updates
1. **Select UniteHebergement**
   - Choose an option from "Unité d'Hébergement" dropdown
   - Wait 1-2 seconds
   - Verify "Chambre" dropdown is now populated (not empty)
   - Check browser console (F12) for network requests to `/api/mouvements/chambres/{uh_id}`

2. **Select Chambre**
   - Choose an option from "Chambre" dropdown
   - Verify "Lit" dropdown is now populated
   - Check browser console for network requests to `/api/mouvements/lits/{chambre_id}`

3. **Select Movement Type**
   - Choose different movement types (A01, A02, etc.)
   - Verify "Raison / Motif" dropdown updates appropriately
   - Check browser console for network requests to `/api/mouvements/reasons/{code}`

#### Test Date Validation
1. **Try Retroactive Date - Before Venue Start**
   - Try submitting with date before venue.start_time
   - Should get error message: "La date du mouvement... ne peut pas être antérieure au début de la venue..."
   - Verify HTTP 400 response in browser console

2. **Try Retroactive Date - Before Last Movement**
   - Select a venue with existing movements
   - Try submitting with date before last movement
   - Should get error message: "La date du mouvement... ne peut pas être antérieure au dernier mouvement..."
   - Verify HTTP 400 response in browser console

3. **Submit Valid Date**
   - Submit form with current or future date
   - Should succeed with HTTP 200/302 response

#### Test Field Removal
- Verify "Localisation complète" field is NOT visible in the form
- Verify only Chambre and Lit fields appear (not full location)

### 3. Browser Developer Tools Inspection

**Open DevTools (F12) and:**

1. **Network Tab**
   - Select UniteHebergement
   - Watch for XHR/Fetch requests
   - Should see: `GET /api/mouvements/chambres/1` (or similar ID)
   - Response should be JSON with `success: true`

2. **Console Tab**
   - No JavaScript errors should appear
   - Script loading should show: `mouvement_dynamic_updates.js` loaded
   - No fetch errors or exceptions

3. **Elements Tab**
   - Inspect the select elements to verify options are populated
   - Check that `<option>` tags appear after AJAX call

### 4. Automated Test Script

Run the provided test helper:

```bash
cd /home/nico/Travail/Fhir_MedBridgeData/MedData_Bridge
python3 test_mouvement_ajax_endpoints.py
```

**Expected Output:**
```
============================================================
MOUVEMENT FORM AJAX ENDPOINTS TEST
============================================================
✓ Server is running at http://127.0.0.1:8000

============================================================
Testing: GET /api/mouvements/chambres/{uh_id}
============================================================
Status: 200
Response: {
  "success": true,
  "options": [...]
}
✓ Found N chambres

============================================================
Testing: GET /api/mouvements/lits/{chambre_id}
============================================================
Status: 200
Response: {
  "success": true,
  "options": [...]
}
✓ Found M lits

============================================================
Testing: GET /api/mouvements/reasons/{movement_type}
============================================================
Status: 200
Response: {
  "success": true,
  "options": [...]
}
✓ Found K reasons

============================================================
TEST COMPLETE
============================================================
```

### 5. Test Data Scenarios

#### Scenario A: Full Success Path
1. Create new mouvement
2. Select UniteHebergement → verify Chambres load
3. Select Chambre → verify Lits load
4. Select Movement Type → verify Reasons load
5. Fill in remaining fields
6. Submit with valid date → should succeed

#### Scenario B: Error Handling
1. Try to submit with retroactive date
2. Verify error message displays
3. Fix date
4. Resubmit → should succeed

#### Scenario C: Field Dependencies
1. Select UH → verify Chambre empties when UH changes
2. Select new UH → verify Chambre repopulates with new options
3. Verify Lit empties when Chambre changes

---

## Expected Behavior Summary

| Action | Expected Behavior |
|--------|---|
| Page Load | Form displays with empty dependent selects |
| Select UH | Chambre select populates via AJAX (1-2 sec delay) |
| Change UH | Chambre options replaced (not appended) |
| Select Chambre | Lit select populates via AJAX |
| Select Movement Type | Reason select populates via AJAX |
| Submit with past date | 400 error with descriptive message |
| Submit with future date | 200/302 success response |
| Location field | Should NOT appear in form |

---

## Troubleshooting

### AJAX Calls Not Working
**Problem:** Chambre/Lit/Reason selects remain empty after selection  
**Solution:**
1. Check browser console (F12) for errors
2. Check Network tab for failed AJAX requests
3. Verify server is running: `curl http://127.0.0.1:8000/mouvements`
4. Check server logs for errors

### 404 Responses from API
**Problem:** AJAX endpoints return 404  
**Solution:**
1. Verify database contains test data (UH, Chambre, Lit)
2. Check if IDs in database are sequential starting from 1
3. Try with different IDs: `/api/mouvements/chambres/2`, etc.

### Date Validation Not Working
**Problem:** Can submit retroactive dates without error  
**Solution:**
1. Check server logs for exceptions
2. Verify venue.start_time is set in database
3. Verify last movement exists for venue
4. Try with a clear past date (e.g., 2020-01-01)

### Form Fields Missing
**Problem:** Expected fields don't appear  
**Solution:**
1. Clear browser cache: Ctrl+F5 (Cmd+Shift+R on Mac)
2. Verify form.html includes mouvement_dynamic_updates.js script
3. Check browser console for JavaScript loading errors

---

## Test Completion Checklist

- [ ] Endpoints respond with 200 status
- [ ] AJAX responses contain valid JSON with success field
- [ ] Chambre list updates when UH changes
- [ ] Lit list updates when Chambre changes
- [ ] Reason list updates when Type changes
- [ ] Date validation prevents retroactive movements
- [ ] Error messages are descriptive and helpful
- [ ] Location field is removed from form
- [ ] No JavaScript errors in console
- [ ] All 3 AJAX endpoints accessible
- [ ] Form submits successfully with valid data

---

## Additional Notes

- **Performance:** Initial page load should be fast (<1s)
- **Cascade Delay:** Expected 200-500ms delay for AJAX calls
- **Browser Compatibility:** Tested on Chrome/Firefox/Safari (all modern versions)
- **Mobile:** Form is responsive and works on tablets/phones
- **Accessibility:** Form includes ARIA attributes and semantic HTML

---

For detailed implementation information, see:
- `MOUVEMENT_FORM_COMPLETION.md`
- `SESSION_SUMMARY.md`
- `app/routers/mouvements.py` (POST handler and AJAX endpoints)
- `app/static/js/mouvement_dynamic_updates.js` (JavaScript implementation)
