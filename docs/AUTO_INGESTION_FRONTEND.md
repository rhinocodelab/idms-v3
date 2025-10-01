# Auto Ingestion Workflow - Frontend Documentation

## Overview
The Auto Ingestion Workflow frontend provides an intuitive interface for administrators to manage automated document processing workflows.

## Files Created

### 1. `app/templates/auto_ingestion.html`
Main frontend page for the Auto Ingestion Workflow system.

### 2. `app/templates/base.html` (Updated)
Added "Auto Ingestion Workflow" submenu under "Upload Documents" (Admin only).

---

## UI Components

### 📊 Dashboard Statistics (KPI Cards)
Four key metrics displayed at the top:
- **Active Workflows**: Count of currently running workflows
- **Processed Today**: Total files processed today
- **In Queue**: Files waiting to be processed
- **Failed**: Files that failed processing

### 🗂️ Workflows List
Grid layout displaying workflow cards with:
- Workflow name and source path
- Current status (Running/Stopped/Paused/Error)
- Scan interval
- Files processed/failed count
- Last scan timestamp
- Action buttons (Start/Stop/Details/Edit/Delete)

### ➕ Create Workflow Modal
Form to create new workflows with fields:
- **Workflow Name**: Unique identifier
- **Source Folder Path**: Directory to monitor
- **Scan Interval**: Time between scans (min 10 seconds)
- **File Types**: PNG, JPEG, JPG only (read-only info)

### 📝 Workflow Details Modal
Comprehensive view of individual workflow with:

**Information Panel:**
- Status, source path, interval
- Last scan time, files processed/failed

**Queue Tab:**
- Table showing queued files
- Columns: File Name, Size, Status, Added Time, Actions
- Retry button for failed items

**Activity Logs Tab:**
- Chronological log entries
- Color-coded by severity (info/success/warning/error)
- File path and timestamp for each entry

---

## API Endpoints Expected (Frontend calls these)

### Workflow Management
- `GET /api/auto-ingestion/dashboard` - Dashboard stats
- `GET /api/auto-ingestion/workflows` - List workflows
- `POST /api/auto-ingestion/workflows` - Create workflow
- `GET /api/auto-ingestion/workflows/{id}` - Get workflow details
- `PUT /api/auto-ingestion/workflows/{id}` - Update workflow
- `DELETE /api/auto-ingestion/workflows/{id}` - Delete workflow

### Workflow Control
- `POST /api/auto-ingestion/workflows/{id}/start` - Start workflow
- `POST /api/auto-ingestion/workflows/{id}/stop` - Stop workflow

### Queue & Logs
- `GET /api/auto-ingestion/queue?workflow_id={id}` - Get queue items
- `POST /api/auto-ingestion/queue/{id}/retry` - Retry failed item
- `GET /api/auto-ingestion/workflows/{id}/logs` - Get activity logs

---

## Security

### Admin-Only Access
- Menu item only visible to users with `role='admin'`
- Frontend checks user role via `{% if user and user.role == 'admin' %}`
- Backend APIs should also verify admin role

### Authentication
- All API calls include `Authorization: Bearer {token}` header
- Token retrieved from `localStorage.getItem('token')`

---

## Next Steps - Backend Implementation

1. Create database tables (3 tables)
2. Implement API endpoints
3. Create background worker logic
4. Implement file scanning
5. Implement queue processing
6. Integrate with AI classification
7. Add file renaming logic
8. Implement logging system
