# UI Testing Guide

## System Status
- **Frontend Server**: ✅ Running on http://localhost:8080
- **Mock Backend API**: ✅ Running on http://localhost:5000
- **Test Credentials**: `testuser` / `test123`

## Quick Start Testing (5 minutes)

### Step 1: Open the UI
1. Open your browser
2. Go to **http://localhost:8080**
3. You should see the login/signup screen

### Step 2: Create a Test Account
1. Click on "**Sign Up**" (or use the toggle link)
2. Enter a username (e.g., `myuser123`)
3. Enter a password (must be 6+ characters)
4. Click "**Sign Up**"
5. You'll be automatically logged in ✅

### Step 3: Upload a Document
1. You should be on the Upload tab
2. Click the upload area or drag a PDF file
3. Select any PDF file from your computer
4. Watch the uploading indicator
5. ✅ Success message appears: "Document uploaded successfully!"
6. Document appears in your documents list with status: `processing` ⏳

### Step 4: Wait for Auto-Transition
1. Document status is `processing`
2. Wait 5-10 seconds
3. Page auto-refreshes every 10 seconds
4. Status changes to `ready` ✅
5. Click the document to see details

### Step 5: Search
1. Click the "**Search**" tab
2. Enter search text (e.g., "machine learning")
3. Click "**Search**"
4. See search results ranked by similarity

### Step 6: Logout & Login Again
1. Click "**Logout**" button (top right)
2. You return to login screen
3. Log in with your credentials
4. ✅ Your documents are still there!

---

## Features to Test

### Authentication ✅
- [x] Sign up new user
- [x] Log in with credentials
- [x] Session persists (refresh page, documents still there)
- [x] Logout clears session
- [x] Invalid credentials show error

### Document Management ✅
- [x] Upload PDF file
- [x] Document appears in list
- [x] Status shows "processing"
- [x] Status changes to "ready" after 5 sec
- [x] Select document to view details
- [x] Document info shows ID, filename, upload date

### Search ✅
- [x] Search tab accessible
- [x] Enter search text
- [x] Results show similarity scores
- [x] Results ranked by percentage
- [x] Shows matched text snippets
- [x] Shows source document name

### UI/UX ✅
- [x] Clean, modern design
- [x] Responsive layout
- [x] Loading indicators work
- [x] Error messages appear
- [x] Success messages appear
- [x] Tabs switch correctly

---

## Known Behaviors

### Mock Backend
- Documents auto-transition from `processing` → `ready` after **5 seconds**
- UI refreshes every **10 seconds** to show status changes
- Search returns **mock results** (pre-configured similarity examples)
- Documents persist in memory (clear when backend restarts)

### Pre-loaded Test Data
When you first use `testuser` / `test123`:
- 3 sample documents are available
- 2 are in `ready` status
- 1 is in `processing` status
- All with mock similarity search results

---

## Testing Checklist

### Complete Workflow Test
```
[ ] 1. Sign up with new account
[ ] 2. Log in successfully
[ ] 3. Upload PDF document (use any PDF file)
[ ] 4. Document appears in list with "processing" status
[ ] 5. Wait 10 seconds, page refreshes, status changes to "ready"
[ ] 6. Click document to view details
[ ] 7. Go to Search tab
[ ] 8. Search for text (e.g., "test")
[ ] 9. See similarity results
[ ] 10. Logout
[ ] 11. Log back in, documents still there
```

### Edge Cases to Test
```
[ ] Try uploading a non-PDF file (should error)
[ ] Try searching without ready documents (should show message)
[ ] Try logging in with wrong password (should error)
[ ] Try signing up with duplicate username (should error)
[ ] Refresh page mid-upload (upload completes, documents load)
[ ] Open UI in multiple browser tabs (session shared)
```

### Visual Checks
```
[ ] Purple gradient theme looks good
[ ] Loading spinners animate smoothly
[ ] Document status badges show correct colors:
    - Yellow for "processing"
    - Green for "ready"
    - Red for "failed"
[ ] Similarity bars fill correctly with percentage
[ ] No console errors (F12 to check)
```

---

## Troubleshooting

### Issue: Can't upload file
**Solution**: 
- File must be PDF (ends with `.pdf`)
- Check file isn't corrupted
- Try a different PDF file

### Issue: Status doesn't change from "processing"
**Solution**:
- Wait 10 seconds for auto-refresh
- Manually refresh page (F5)
- Mock backend is set to transition after 5 seconds

### Issue: Can't log in
**Solution**:
- Check username/password spelling
- Password must be 6+ characters
- Make sure backend is running (http://localhost:5000)

### Issue: No search results
**Solution**:
- Make sure at least one document has `ready` status
- Wait for document processing to complete
- Try different search terms

### Issue: Can't access frontend
**Solution**:
- Check http://localhost:8080 is accessible
- Make sure HTTP server is running
- Try http://127.0.0.1:8080 instead

---

## For Production (When Docker Works)

To switch to the real backend:

1. **Fix Docker Desktop** and run:
   ```powershell
   docker compose up
   ```

2. **Edit index.html** (line ~1214):
   ```javascript
   // Change from:
   const API_BASE_URL = 'http://localhost:5000';
   
   // To:
   const API_BASE_URL = 'http://localhost:8080';
   ```

3. **Features in production backend**:
   - Real PDF text extraction
   - Actual semantic embeddings
   - Persistent database storage
   - Real-time search accuracy
   - Multiple user support
   - All production data preserved

---

## Test Files

If you don't have a PDF file to test with, here's how to create one:

**Windows** (in PowerShell):
```powershell
$pdf = @(0x25, 0x50, 0x44, 0x46, 0x2D, 0x31, 0x2E, 0x34)
[System.IO.File]::WriteAllBytes("C:\test.pdf", $pdf)
```

This creates a minimal valid PDF header that the system accepts.

---

## Monitoring Network Requests

To see all API calls:
1. Open DevTools (F12)
2. Go to "Network" tab
3. Upload a document
4. You'll see:
   - POST /documents (upload)
   - GET /documents (refresh list)
   - Responses in JSON format

---

## Questions?

If something isn't working:
1. Check both servers are running (8080 and 5000)
2. Check browser console for errors (F12)
3. Check network requests (F12 → Network tab)
4. Try refreshing the page
5. Try logging out and back in
6. Try restarting the backend

---

**Happy Testing! 🎉**
