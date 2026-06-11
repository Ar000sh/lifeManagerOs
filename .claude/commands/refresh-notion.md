# /refresh-notion — Sync Notion Structure

Re-crawl the entire Notion workspace and update `context/notion.md` to reflect the current state.
Run this whenever pages are added/removed, databases are restructured, or schemas change.

## Steps

### 1. Fetch the root and all top-level section pages in parallel
- Root: `17f640b8-4c57-4cdb-8cb8-7de20d282e14`
- Business: `02b35e4e-891d-4c3b-a8a1-8b5f3a968c34`
- University: `25a31bbe-c66a-42d7-abd1-063ddf316f0e`
- Work: `eb3dd869247246a0871a97ff7580d707`

### 2. Fetch all known sub-pages and collections in parallel
Business sub-pages:
- Laundromat Hannover: `39b55afae5704875a1641799948d8e38`
- Van Company Czech Republic: `b5397190ebbf48fb98d8f6de7f410790`

Collections (fetch via collection:// URL to get full schema):
- Laundromat Tasks: `collection://fdffad80-a34c-44a0-a9ed-afb05acd232e`
- Van Company Tasks: `collection://ae28ef1d-5dec-45d2-b3ab-8132214d5361`
- Modules: `collection://5e62acec-3f74-49f7-a8b2-c4b6937ca4b3`
- University Tasks: `collection://580c2d1d-8813-4800-92a1-9db78568a1ca`
- Work Schedule: `collection://55f90404-8783-412a-9f9d-e6d5011bcc7a`

### 3. Detect changes
Compare what you just fetched against `context/notion.md`. Look for:
- New pages or sub-pages under any section
- Removed pages
- New or renamed database properties
- New select/option values added to existing properties
- New databases added to any page
- Any collection URL that has changed

### 4. Update context/notion.md
Rewrite `context/notion.md` to reflect the current state exactly. Preserve the existing format and structure — only update the parts that changed.

Also update `context/integrations.md` if any new MCP tools or connections are detected.

### 5. Report
Tell the user what changed in a short summary:
- "X new pages found: ..."
- "Schema changes in [DB]: ..."
- "Nothing changed, context is up to date."

If new top-level sections or business projects were added that aren't covered by the existing commands (`/today`, `/add`, `/week`), flag them:
> "⚠️ New section '[Name]' found — consider updating the commands to include it."
