# Google Apps Script Guidelines

- Always include `/**@OnlyCurrentDoc */` at the very top of all Google Apps Script (`.js` / `.gs`) files.
- This ensures OAuth scope is restricted strictly to the active spreadsheet (`https://www.googleapis.com/auth/spreadsheets.currentonly`), preventing broad Google Drive access requests.
