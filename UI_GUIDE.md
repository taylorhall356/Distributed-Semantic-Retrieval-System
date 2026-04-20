# UI User Guide

## Overview
A modern, user-friendly web interface for the Distributed Semantic Retrieval System. Built with vanilla JavaScript, CSS, and HTML - no external dependencies required beyond what the backend provides.

## Features

### 🔐 Authentication
- **Sign Up**: Create a new user account
- **Log In**: Access your existing account
- Secure JWT token-based authentication
- Session persists in browser local storage

### 📤 Upload Tab
**Left Sidebar:**
- **Upload Area**: Drag & drop or click to upload PDF documents
- **Loading Indicator**: Shows upload and processing status
- **Document List**: View all your uploaded documents with status badges
  - 🟡 `processing` - Document being extracted and indexed
  - 🟢 `ready` - Document ready for search
  - 🔴 `failed` - Processing failed

**Main Content:**
- **Document Information**: View details of selected document
- See upload date and current processing status
- Organized document metadata display

### 🔍 Search Tab
**Search Interface:**
- **Text Input**: Enter any text, question, or phrase to search
- **Search Button**: Find similar content across all ready documents
- Shows processing info (number of documents being searched)

**Search Results:**
- **Similarity Score**: Visual bar showing relevance percentage (0-100%)
- **Document Name**: Which document the result came from
- **Matched Text**: The actual text snippet from the document
- **Ranked Results**: Top matches sorted by relevance

## How to Use

### 1. Getting Started
1. Open `http://localhost:8080` in your web browser
2. Sign up with a username and password
3. Or log in if you already have an account

### 2. Upload Documents
1. Click the **Upload Tab** if not already there
2. Drag PDF files into the upload area or click to select
3. Wait for the upload to complete
4. Document will be added to **Your Documents** list
5. Status shows as `processing` while text is being extracted and indexed
6. Status changes to `ready` when ready for search (typically 10-30 seconds per document)

### 3. Search Your Documents
1. Click the **Search Tab**
2. Enter text you want to find:
   - Questions: "What is machine learning?"
   - Keywords: "neural networks"
   - Phrases: "supervised learning models"
3. Click **Search** (or Ctrl+Enter)
4. Results appear ranked by similarity
5. Each result shows:
   - **Similarity Score** (percentage)
   - **Document Name**
   - **Matching Text Excerpt**

### 4. Manage Documents
- Click any document in the list to view its details
- Documents with `ready` status are searchable
- Delete documents using the browser's developer tools or via API (UI button coming soon)

## UI Components

### Color Scheme
- **Primary**: Purple gradient (#667eea → #764ba2)
- **Success**: Green (#4caf50)
- **Warning**: Yellow (#ffd700)
- **Error**: Red (#f44336)

### Responsive Design
- **Desktop**: Two-column layout (sidebar + content)
- **Mobile**: Stacked layout (adapts automatically)
- Works on tablets, phones, and desktops

### Accessibility
- Clear visual feedback for all actions
- Loading states for long operations
- Error messages for failed operations
- Keyboard shortcuts (Ctrl+Enter to search)

## Technical Details

### Frontend Stack
- **HTML5**: Semantic markup
- **CSS3**: Modern styling with flexbox/grid
- **Vanilla JavaScript**: No framework dependencies

### API Integration
- Connects to existing FastAPI backend
- JWT authentication for secure access
- CORS-enabled for cross-origin requests
- Real-time document status updates

### Local Storage
- Stores authentication token
- Stores username for session persistence
- Clears on logout

## Troubleshooting

### Issue: Can't connect to backend
**Solution**: Make sure the backend is running on `http://localhost:8080`
```powershell
docker compose up
```

### Issue: Upload fails
**Solution**: 
- Check file is PDF (not corrupted)
- File size under 50MB
- Refresh page and try again

### Issue: Search returns no results
**Solution**:
- Wait for documents to reach `ready` status
- Try different search terms
- Check document content is being processed correctly

### Issue: Authentication fails
**Solution**:
- Clear browser cache and local storage
- Try a different username
- Check backend is responding to auth endpoints

## Browser Requirements
- Modern browser with JavaScript enabled
- Local storage support
- No plugins or extensions required
- Works on Chrome, Firefox, Safari, Edge

## Future Enhancements
- Bulk document upload
- Document preview/viewer
- Advanced search filters
- Export search results
- User profile management
- Document sharing
- OCR for scanned PDFs
