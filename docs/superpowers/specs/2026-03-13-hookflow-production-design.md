# HookFlow - Production-Ready Design Spec

**Date:** 2026-03-13
**Status:** Approved
**Author:** Claude (autonomous-coding session)

---

## Executive Summary

Transform HookFlow from MVP to production-ready SaaS platform through three sequential phases:
- **Phase 2:** Complete dashboard with webhook logs, analytics, destination management, API keys
- **Phase 3:** Remaining integrations (Database, Email, Notion, Airtable, Google Sheets)
- **Phase 5:** Multi-tenant authentication and Stripe billing

---

## Phase 2: Dashboard & Core Features

### 2.1 Dashboard Pages (Next.js App Router)

#### Route Structure
```
/dashboard                    # Overview with stats
/dashboard/app/[id]           # App detail page
/dashboard/app/[id]/webhooks  # Webhook log viewer
/dashboard/app/[id]/webhooks/[id]  # Individual webhook detail
/dashboard/app/[id]/destinations  # Destination management
/dashboard/app/[id]/settings   # App settings & API keys
```

#### Page Specifications

**`/dashboard` - Overview**
- Cards showing: webhooks today, success rate (24h), active destinations, monthly usage
- Mini chart: webhooks per day (last 7 days)
- Quick actions: "Create App", "Add Destination"
- Recent webhooks table (last 10)

**`/dashboard/app/[id]` - App Detail**
- App info: name, description, webhook URL (copyable)
- Stats cards: total webhooks, success rate, avg response time
- Active destinations list with status indicators
- Recent webhook activity

**`/dashboard/app/[id]/webhooks` - Webhook Log Viewer**
- Paginated table (default 50 per page)
- Filters: status, date range, source IP
- Search: by body content
- Columns: timestamp, status, source, summary
- Row click → detail page

**`/dashboard/app/[id]/webhooks/[id]` - Webhook Detail**
- Full webhook payload (JSON viewer)
- Request headers
- Delivery attempts timeline:
  - Destination name
  - Status badge (success/failed/retrying)
  - Response code & time
  - Error message (if failed)
  - Retry count
- Replay button (with destination selector)

**`/dashboard/app/[id]/destinations` - Destination Management**
- List view: name, type, status, last delivery
- Add/Edit destination dialog
- Type-specific config forms
- Test destination button

**`/dashboard/app/[id]/settings` - App Settings**
- App name, description (editable)
- Signature verification toggle
- Retention period selector
- API Keys section:
  - List existing keys (name, prefix, last used, expires)
  - Create new key button
  - Revoke button
  - Copy key button

### 2.2 New API Endpoints

#### Analytics
```
GET /api/v1/analytics/{app_id}
Query Params: ?period=24h|7d|30d
Response: {
  total_webhooks: number,
  success_rate: number,
  avg_response_time_ms: number,
  webhooks_by_status: { pending: 0, processing: 0, completed: 0, failed: 0 },
  webhooks_over_time: [{ timestamp, count }],
  top_destinations: [{ name, count, success_rate }]
}
```

#### API Keys
```
POST /api/v1/apps/{app_id}/api-keys
Request: { name: string, scopes: string[], expires_at?: datetime }
Response: { id, name, key, key_prefix, scopes, expires_at, created_at }

GET /api/v1/apps/{app_id}/api-keys
Response: [{ id, name, key_prefix, scopes, last_used_at, expires_at, created_at }]

DELETE /api/v1/apps/{app_id}/api-keys/{key_id}
Response: 204 No Content
```

#### Real-time Status (SSE)
```
GET /api/v1/apps/{app_id}/events/stream
Headers: Accept: text/event-stream
Events:
  - webhook.received: { webhook_id, status, timestamp }
  - delivery.success: { webhook_id, destination_id, response_time_ms }
  - delivery.failed: { webhook_id, destination_id, error }
  - delivery.retrying: { webhook_id, destination_id, attempt_number }
```

### 2.3 Frontend Components to Create

```
components/
├── dashboard/
│   ├── stat-card.tsx          # Stats card with icon/value/change
│   ├── webhook-table.tsx      # Paginated webhook list
│   ├── webhook-detail.tsx     # Full webhook view + deliveries
│   ├── delivery-timeline.tsx  # Visual delivery attempts
│   ├── destination-list.tsx   # Destinations with status
│   ├── destination-form.tsx   # Add/edit destination
│   ├── api-key-list.tsx       # API key management
│   └── event-stream.tsx       # SSE hook for real-time updates
├── charts/
│   ├── webhook-chart.tsx      # Webhooks over time (line/bar)
│   └── status-donut.tsx       # Status distribution
└── ui/
    ├── json-viewer.tsx        # Collapsible JSON display
    └── status-badge.tsx       # Delivery status badges
```

---

## Phase 3: Integrations

### 3.1 Database Destination

**Type:** `database`

**Config Schema:**
```typescript
{
  table_name?: string,  // Auto-generates if not provided: "webhooks_{app_id}"
  create_table: boolean = true  // Auto-create table if missing
}
```

**Implementation:**
- New model: `DatabaseDestination` table mapping
- Service method: `_deliver_database()`
- Auto-creates table with columns: id, webhook_id, app_id, body, headers, created_at
- Inserts webhook payload as JSONB

### 3.2 Email Integration

**Type:** `email`

**Config Schema:**
```typescript
{
  provider: "sendgrid" | "ses" | "smtp",
  to: string[],
  subject?: string,
  from?: string,
  template_id?: string  // For SendGrid templates
}
```

**Implementation:**
- SendGrid client for provider=sendgrid
- Boto3 SES client for provider=ses
- SMTP for provider=smtp
- Formats webhook body as HTML table

### 3.3 Notion Integration

**Type:** `notion`

**Config Schema:**
```typescript
{
  api_key: string,
  database_id: string,
  field_mappings: {
    // Map webhook JSON paths to Notion properties
    "webhook.field": "notion_property_id"
  }
}
```

**Implementation:**
- Notion API client
- Creates new page in database
- Maps fields according to mapping config

### 3.4 Airtable Integration

**Type:** `airtable`

**Config Schema:**
```typescript
{
  access_token: string,
  base_id: string,
  table_id: string,
  field_mappings: { [webhook_path]: string }
}
```

**Implementation:**
- Airtable REST API client
- Creates records with mapped fields

### 3.5 Google Sheets Integration

**Type:** `google_sheets`

**Config Schema:**
```typescript
{
  spreadsheet_id: string,
  sheet_name?: string,  // Default: "Sheet1"
  credentials: { /* OAuth2 credentials JSON */ },
  field_mappings: { [webhook_path]: column_index }
}
```

**Implementation:**
- Google Sheets API v4
- OAuth2 token refresh
- Appends rows with mapped values

---

## Phase 5: Authentication & Billing

### 5.1 Authentication Strategy

**Recommended:** Clerk (easier than Auth0, great Next.js integration)

**Setup:**
1. Install `@clerk/nextjs`
2. Add middleware for protected routes
3. Wrap app with `<ClerkProvider>`
4. Update database: link `apps.user_id` to Clerk user ID

**Alternative:** Custom JWT auth
- Login/register endpoints
- JWT token generation
- Protected route middleware

### 5.2 Stripe Billing

**Plan Tiers (existing in models):**
- FREE: 1K events/mo, 24h retention
- PRO: 100K events/mo, 30d retention, $29/mo
- TEAM: 500K events/mo, 90d retention, $99/mo
- ENTERPRISE: Custom

**Implementation:**

1. **Stripe Products/Prices** - Create in Stripe dashboard
2. **Checkout Flow:**
   - POST /billing/checkout - Creates Stripe Checkout session
   - Redirect to Stripe hosted checkout
   - Stripe webhook on success → update subscription

3. **Webhook Handler:**
   - POST /api/v1/billing/webhook - Stripe signature verified
   - Handles: checkout.session.completed, customer.subscription.updated, deleted

4. **Usage Tracking:**
   - Background job: count webhooks per app each day
   - Store in `usage_history` table
   - Check limits on webhook receive

5. **Feature Flags by Plan:**
   ```python
   def can_use_feature(app: App, feature: str) -> bool:
       limits = {
           "free": {"retention_hours": 24, "destinations": 3},
           "pro": {"retention_hours": 720, "destinations": 20},
           "team": {"retention_hours": 2160, "destinations": -1},  # unlimited
       }
       return limits[app.plan_tier][feature]
   ```

---

## Data Model Additions

### New Tables

**`usage_history`**
```sql
CREATE TABLE usage_history (
  id UUID PRIMARY KEY,
  app_id UUID REFERENCES apps(id),
  period DATE NOT NULL,  -- YYYY-MM
  webhook_count INTEGER DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

**`subscriptions` (if using Stripe)**
```sql
CREATE TABLE subscriptions (
  id UUID PRIMARY KEY,
  user_id UUID REFERENCES users(id),
  stripe_customer_id VARCHAR(255),
  stripe_subscription_id VARCHAR(255),
  stripe_price_id VARCHAR(255),
  status VARCHAR(50),  -- active, canceled, past_due
  current_period_start TIMESTAMPTZ,
  current_period_end TIMESTAMPTZ,
  cancel_at_period_end BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## Implementation Priority

1. **Phase 2a:** Dashboard pages (all routes above)
2. **Phase 2b:** Analytics API + frontend charts
3. **Phase 2c:** API key management
4. **Phase 2d:** Real-time status (SSE)
5. **Phase 3a:** Database destination
6. **Phase 3b:** Email integration
7. **Phase 3c:** Notion integration
8. **Phase 3d:** Airtable integration
9. **Phase 3e:** Google Sheets integration
10. **Phase 5a:** Authentication (Clerk)
11. **Phase 5b:** Stripe billing integration

---

## Success Criteria

### Phase 2
- [ ] User can view all webhooks with pagination
- [ ] User can see delivery status for each webhook
- [ ] User can replay failed webhooks
- [ ] Real-time delivery updates visible on dashboard
- [ ] API keys can be created/revoked
- [ ] Analytics show delivery rates and trends

### Phase 3
- [ ] Webhooks can be stored to database
- [ ] Webhooks can be sent via email
- [ ] Webhooks can create Notion pages
- [ ] Webhooks can create Airtable records
- [ ] Webhooks can append to Google Sheets

### Phase 5
- [ ] Users can sign up/login
- [ ] Users see only their own apps
- [ ] Users can upgrade to paid plans via Stripe
- [ ] Usage limits are enforced
- [ ] Webhooks are blocked when limit exceeded

---

## Notes

- Existing codebase uses FastAPI + SQLAlchemy + Next.js 14 + Tailwind
- Queue system: Redis (production) / in-memory (dev)
- All new endpoints need proper error handling
- Frontend should use existing UI component library
- Follow existing code patterns and conventions
