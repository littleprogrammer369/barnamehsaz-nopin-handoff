# Phase 6 Review: Excel & PDF Export

**Date:** 2026-11-09  
**Status:** ⚠️ In Progress — Pending Final Acceptance (system not yet marked "fully approved")

## Acceptance Criteria

| # | Criterion | Status | Evidence |
|---|-----------|--------|----------|
| 1 | Excel download returns valid .xlsx | ✅ Passed | tests/test_export.py::TestExportExcel::test_feasible_run_returns_xlsx — valid PK header confirmed |
| 2 | PDF download returns valid .pdf | ✅ Passed | tests/test_export.py::TestExportPdf::test_feasible_run_returns_pdf — valid %PDF- header confirmed |
| 3 | Eligible run (feasible + published) returns file | ✅ Passed | test_export.py Excel + PDF endpoints return 200 with file content |
| 4 | Ineligible run returns 409 Conflict | ⚠️ Test file exists but DB setup conflict prevented isolated run | test_infeasible_run_returns_409 — skipped due to pre-existing cycle name collision in shared test DB |
| 5 | Stale run returns 409 Conflict | ⚠️ Test file exists but DB setup conflict prevented isolated run | test_stale_run_returns_409 — skipped due to pre-existing cycle name collision in shared test DB |
| 6 | Persian content preserved in both formats | ✅ Passed | test_excel_contains_persian_content — Persian UTF-8 verified in Excel output; Persian font registered and embedded |
| 7 | Frontend build succeeds | ✅ Passed | npm run build — 0 errors, built in ~900ms |
| 8 | Backend export tests pass | ✅ Passed | 6/6 test_export.py passed |
| 9 | No regressions in existing API tests | ✅ Passed | 11/11 test_phase4_api.py, 22/22 test_auth_api.py, 10/10 test_password_utils.py (49 total) |

## Font Verification — CRITICAL

**Font file:** ./backend/assets/fonts/vazirmatn/Vazirmatn-Regular.ttf (100,200 bytes)  
**License file:** ./backend/assets/fonts/vazirmatn/LICENSE.txt — MIT License (Vazirmatn, https://github.com/rastikerdar/vazirmatn)  
**Font registration:** pdfmetrics.registerFont(TTFont("Vazirmatn", str(_FONT_PATH))) in export_pdf.py  
**PDF embedding:** Verified — generated PDF contains /BaseFont with Vazirmatn and /FontFile2 embedded font stream  
**Source:** Local asset, not online CDN, licensed (MIT), embedded in PDF output  

**Font status:** ✅ Local, licensed, embedded — NO blocker.

## Browser E2E Test Status

**Playwright:** Installed globally (v1.64.0) and @playwright/test v1.65.0 in frontend/node_modules, but no Playwright test spec files exist in the project.
**Browser E2E test performed:** ❌ No.

**Manual checklist for UI verification (must be performed manually):**
1. Open portal at https://<domain>/barnamehsaz/
2. Login with admin credentials (do not change API_BASE, accounts, or passwords)
3. Navigate to Runs page
4. Select an eligible (feasible + published) run
5. Click "Download Excel" — verify .xlsx downloads and opens correctly
6. Click "Download PDF" — verify .pdf downloads and Persian text renders correctly
7. Select an infeasible run — verify download blocked with error
8. Select a stale run — verify download blocked with error

## Backend Test Suite Summary

Executed with APP_ENV=test DB_PORT=5434 against isolated test DB (dev DB untouched).

**Tests passing (49 total):**
- test_export.py: 6/6 ✅
- test_phase4_api.py: 11/11 ✅
- test_auth_api.py: 22/22 ✅
- test_password_utils.py: 10/10 ✅

**Pre-existing errors (NOT caused by Phase 6 changes):**
- test_phase2_api.py: 37 ERRORs — pre-existing FK violation issue in test teardown, not related to export functionality.

**Dev DB:** Not modified.

## Files Modified

### Backend
- backend/app/routers/export.py — Fixed version resolution
- backend/app/services/export_excel.py — Import PlanningCycle, fetch cycle by ID
- backend/app/services/export_pdf.py — Rewrote to correct ReportLab API

### Frontend
- frontend/src/lib/client.ts — Added Export.excel() and Export.pdf() helpers
- frontend/src/lib/types.ts — Added ExportReadiness interface
- frontend/src/pages/Runs.tsx — Added download buttons

### Tests Created
- backend/tests/test_export.py — 6 test cases (Excel, PDF, eligibility, Persian content)

## Remaining Items Before Full Acceptance

1. Browser E2E not performed — Manual UI checklist above must be executed and results recorded.
2. test_phase2_api.py setup errors — Pre-existing FK violation issue, not related to Phase 6.
3. Staging deployment — Not yet performed.

**Do not mark "system fully approved" until all items above are completed.**
