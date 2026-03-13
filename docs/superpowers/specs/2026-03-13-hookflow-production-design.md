# HookFlow - Production-Ready Design Spec

**Date:** 2026-03-13
**Status:** Draft - v2 (addressing review feedback)
**Author:** Claude (autonomous-coding session)

---

## Executive Summary

Transform HookFlow from MVP to production-ready SaaS platform through three sequential phases:

**Phase Context:**
- **Phase 1 (COMPLETE):** MVP foundation - webhook receiving, storage, basic delivery, retry logic, HTTP/Slack/Discord/Telegram destinations
- **Phase 2:** Dashboard with webhook logs, analytics, destination management, API keys
- **Phase 3:** Remaining integrations (Database, Email, Notion, Airtable, Google Sheets)
- **Phase 4:** Advanced features (AI transformation, debugging proxy, custom domains) - out of scope for this spec
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
- Mini chart: webhooks per day (last 7 days) using `recharts`
- Quick actions: "Create App", "Add Destination"
- Recent webhooks table (last 10)

**`/dashboard/app/[id]` - App Detail**
- App info: name, description, webhook URL (copyable) at `/api/v1/webhook/{app_id}`
- Stats cards: total webhooks, success rate, avg response time
- Active destinations list with status indicators
- Recent webhook activity

**`/dashboard/app/[id]/webhooks` - Webhook Log Viewer**
- Paginated table (default 50 per page)
- Filters:
  - `status`: pending|processing|completed|failed
  - `start_date`: ISO 8601 date (e.g., `2024-01-01`)
  - `end_date`: ISO 8601 date (e.g., `2024-01-31`)
  - `source_ip`: string match
- Search: by body content (JSON search)
- Columns: timestamp, status, source, summary
- Row click → detail page

**`/dashboard/app/[id]/webhooks/[id]` - Webhook Detail**
- Full webhook payload (collapsible JSON viewer)
- Request headers
- Delivery attempts timeline:
  - Destination name
  - Status badge (success/failed/retrying)
  - Response code & time
  - Error message (if failed)
  - Retry count
- Replay button (with destination selector) - NOTE: Replay endpoint already exists at `/api/v1/webhooks/{webhook_id}/replay`

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
GET /api/v1/apps/{app_id}/analytics
Query Params: ?period=24h|7d|30d

Response:
{
  total_webhooks: number,
  success_rate: number,
  avg_response_time_ms: number,
  webhooks_by_status: { pending: 0, processing: 0, completed: 0, failed: 0 },
  webhooks_over_time: [{ timestamp: "2024-01-01T00:00:00Z", count: 123 }],
  top_destinations: [{ name: string, count: number, success_rate: number }]
}

Implementation:
- New service: AnalyticsService(db: AsyncSession)
- Method: get_analytics(app_id: str, period: str) -> AnalyticsResponse
- SQL aggregation with GROUP BY for time-series data
- Uses PostgreSQL's date_trunc for bucketing timestamps
```

#### API Keys
```
POST /api/v1/apps/{app_id}/api-keys
Request: { name: string, scopes: string[], expires_at?: datetime }
Response (ApiKeyCreateResponse): {
  id: string,
  name: string,
  key: string,  // FULL KEY - only shown once!
  key_prefix: string,
  scopes: string[],
  expires_at: datetime,
  created_at: datetime
}

GET /api/v1/apps/{app_id}/api-keys
Response (ApiKeyResponse[]): [{
  id: string,
  name: string,
  key_prefix: string,  // PREFIX ONLY - not the full key
  scopes: string[],
  last_used_at: datetime,
  expires_at: datetime,
  created_at: datetime
}]

DELETE /api/v1/apps/{app_id}/api-keys/{key_id}
Response: 204 No Content

POST /api/v1/apps/{app_id}/destinations/{id}/test
Request: { test_payload?: object }  // Optional test payload, defaults to sample webhook
Response: {
  success: boolean,
  response_time_ms: number,
  status_code?: number,
  error?: string
}

Implementation:
- New model methods in hookflow.models/app.py (ApiKey model already exists)
- Service: ApiKeyService for create/list/revoke operations
- API key generation: secrets.token_urlsafe(32)
- Hash storage: hashlib.sha256(key.encode()).hexdigest() for key_hash field
- **last_used_at Update:** Middleware updates this field on successful API key validation.
  Create hookflow/api/dependencies.py with auth middleware that updates ApiKey.last_used_at
  on each authenticated request.
```

#### Real-time Status (SSE)
```
GET /api/v1/apps/{app_id}/events/stream
Headers: Accept: text/event-stream
Response: Server-Sent Events stream

Events:
  event: webhook.received
  data: {"webhook_id": "...", "status": "pending", "timestamp": "..."}

  event: delivery.success
  data: {"webhook_id": "...", "destination_id": "...", "response_time_ms": 123}

  event: delivery.failed
  data: {"webhook_id": "...", "destination_id": "...", "error": "..."}

  event: delivery.retrying
  data: {"webhook_id": "...", "destination_id": "...", "attempt_number": 2}

Implementation:
- Library: sse-starlette for FastAPI SSE support
- Architecture: Redis pub/sub for production, in-memory broadcaster for dev
- New service class: hookflow/services/event_broadcaster.py with:
  - EventBroadcaster base class with publish/subscribe methods
  - RedisEventBroadcaster using Redis pub/sub
  - InMemoryEventBroadcaster using asyncio queues (dev only)
- Publisher: delivery worker publishes events on completion via broadcaster.publish()
- Frontend: EventSource hook in components/dashboard/event-stream.tsx
- Reconnection: Auto-reconnect with exponential backoff:
  - Initial delay: 1 second
  - Multiplier: 1.5x
  - Max delay: 30 seconds
  - Max retries: unlimited (reconnects until explicitly closed)
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
│   ├── webhook-chart.tsx      # Webhooks over time (line/bar) - uses recharts
│   └── status-donut.tsx       # Status distribution - uses recharts
└── ui/
    ├── json-viewer.tsx        # Collapsible JSON display
    └── status-badge.tsx       # Delivery status badges
```

### 2.4 Libraries
- **Charts:** `recharts` - React charting library with good TypeScript support
- **JSON Viewer:** Custom component using recursive render with collapse/expand
- **SSE:** Browser native `EventSource` API wrapped in React hook

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
- New delivery method: `_deliver_database(webhook, destination)`
- Auto-creates table with exact schema:
```sql
CREATE TABLE IF NOT EXISTS {table_name} (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  webhook_id UUID NOT NULL,
  app_id UUID NOT NULL,
  body JSONB NOT NULL,
  headers JSONB,
  source_ip VARCHAR(45),
  created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_{table_name}_webhook_id ON {table_name}(webhook_id);
CREATE INDEX IF NOT EXISTS idx_{table_name}_created_at ON {table_name}(created_at DESC);
```
- Inserts webhook payload as JSONB for queryability
- Follows same retry logic as HTTP destinations
- **Schema Evolution Strategy:** JSONB storage allows flexible schema without migrations.
  New fields are automatically stored. Deleted fields have no impact.
  The raw body column preserves complete original JSON for debugging.

### 3.2 Email Integration

**Type:** `email`

**Config Schema:**
```typescript
{
  provider: "sendgrid" | "ses" | "smtp",
  to: string[],  // Array of recipient emails
  subject?: string,  // Default: "New webhook from {app_name}"
  from?: string,  // Required for SMTP, optional for others
  template_id?: string  // For SendGrid templates
}
```

**Default HTML Template:**
```html
<!DOCTYPE html>
<html>
<body>
  <h2>New Webhook Received</h2>
  <table>
    <tr><td><strong>App:</strong></td><td>{{ app_name }}</td></tr>
    <tr><td><strong>Webhook ID:</strong></td><td>{{ webhook_id }}</td></tr>
    <tr><td><strong>Timestamp:</strong></td><td>{{ created_at }}</td></tr>
  </table>
  <h3>Payload:</h3>
  <pre>{{ body_json }}</pre>
</body>
</html>
```

**Implementation:**
- SendGrid: `sendgrid` Python package, uses `/mail/send` endpoint
- SES: `boto3` AWS SDK, uses `send_email` or `send_templated_email`
- SMTP: `smtplib` with SSL/TLS support
- Custom Jinja2 templates: allow `template_body` in config for custom HTML

### 3.3 Notion Integration

**Type:** `notion`

**Config Schema:**
```typescript
{
  api_key: string,
  database_id: string,
  field_mappings: {
    // Map webhook JSON paths to Notion property IDs with types
    "webhook.event": {
      property_id: "title_property_id",
      type: "title"
    },
    "webhook.user_id": {
      property_id: "number_property_id",
      type: "number"
    },
    "webhook.status": {
      property_id: "select_property_id",
      type: "select"
    }
  }
}
```

**Property Type Handling:**
- `title`: String, becomes page title
- `rich_text`: String, creates text block
- `number`: Converts value to number
- `select`: Must match existing select option
- `date`: ISO 8601 datetime string
- `checkbox`: Boolean value
- `email`: Email string
- `url`: URL string

**Implementation:**
- Notion API client using `notion-client` Python package
- Creates new page in database with mapped properties
- Validates property types before API call
- Returns 400 if value doesn't match property type

### 3.4 Airtable Integration

**Type:** `airtable`

**Config Schema:**
```typescript
{
  access_token: string,  // Personal Access Token
  base_id: string,
  table_id: string,
  field_mappings: {
    // Map webhook paths to Airtable field names
    "webhook.event": "Event Name",
    "webhook.user_id": "User ID"
  }
}
```

**Implementation:**
- Airtable REST API v0 using `pyairtable` package
- Creates records with mapped fields
- Follows same retry logic as HTTP destinations
- Returns Airtable record ID in delivery response

### 3.5 Google Sheets Integration

**Type:** `google_sheets`

**Config Schema:**
```typescript
{
  spreadsheet_id: string,
  sheet_name?: string,  // Default: "Sheet1"
  field_mappings: {
    // Map webhook paths to column letters (A, B, C, etc.)
    "webhook.event": "A",
    "webhook.user_id": "B"
  }
}
```

**OAuth2 Flow (Security Fix):**
1. Google Cloud Service Account credentials stored as ENV VAR: `GOOGLE_CLOUD_CREDENTIALS_PATH`
2. Service account JSON loaded server-side at startup, never exposed to users
3. Uses server-to-server auth with private key (no refresh token needed)
4. Access tokens auto-generated per request, expire after 1 hour
5. Users only provide spreadsheet_id and sheet_name in destination config

**NOTE:** No admin UI required. Google credentials are system-level configuration,
not per-destination. Uses service account auth (not user OAuth) for simplicity.

**Implementation:**
- Google Sheets API v4 using `google-api-python-client`
- OAuth2 token management with `google-auth`
- Appends rows with mapped values
- Batch insert support for multiple rows

### 3.6 Integration Error Handling

All integration deliveries follow the same error handling pattern:
1. API/SDK exceptions caught and logged
2. Delivery marked as `failed`
3. Retry scheduled with exponential backoff (if not over max_retries)
4. After max retries, moved to dead letter queue
5. Error message includes API-specific details for debugging

---

## Phase 5: Authentication & Billing

### 5.1 Authentication Strategy

**Recommended:** Clerk (easier than Auth0, great Next.js integration)

**Migration Path (IMPORTANT):**
- Current `User` model with email/password will be DEPRECATED
- Clerk becomes the source of truth for authentication
- Existing `apps.user_id` values will be migrated to Clerk user IDs
- New users go through Clerk sign-up flow
- **Action required:** Users will need to re-authenticate via Clerk on first migration login

**Clerk Migration Process:**
1. Pre-migration: Add `clerk_user_id` column to apps table (nullable initially)
2. Run migration script: `/backend/hookflow/scripts/migrate_to_clerk.py`
   - Creates mapping table: old_user_id -> clerk_user_id
   - Updates apps.user_id in batches of 1000
   - Logs all migrations for audit trail
3. Keep old User table for 30 days for rollback capability
4. Send email notification to all users about re-authentication
5. Post-migration: Remove password_hash from User model (kept for 30-day rollback window)

**Setup:**
1. Install `@clerk/nextjs`
2. Add middleware for protected routes:
```typescript
// middleware.ts
import { clerkMiddleware, createRouteMatcher } from '@clerk/nextjs/server'

const isProtectedRoute = createRouteMatcher(['/dashboard(.*)'])

export default clerkMiddleware((auth, req) => {
  if (isProtectedRoute(req)) auth().protect()
})
```
3. Wrap app with `<ClerkProvider>`
4. Update database: `apps.user_id` stores Clerk user ID (varchar(255))
5. Remove password_hash from User model (kept for backward compatibility during migration)

**Alternative:** Custom JWT auth (if Clerk not desired)
- Login/register endpoints in FastAPI
- JWT token generation using `python-jose`
- Protected route middleware verifying JWT signature
- Refresh token rotation for security

### 5.2 Stripe Billing

**Plan Tiers (existing in models):**
- FREE: 1K events/mo, 24h retention
- PRO: 100K events/mo, 30d retention, $29/mo
- TEAM: 500K events/mo, 90d retention, $99/mo
- ENTERPRISE: Custom

**Implementation:**

1. **Stripe Products/Prices** - Create in Stripe dashboard
2. **Checkout Flow:**
   - `POST /billing/checkout` - Creates Stripe Checkout session
   - Redirect to Stripe hosted checkout
   - Stripe webhook on success → update subscription

3. **Webhook Handler (CRITICAL SECURITY):**
   - `POST /api/v1/billing/webhook`
   - **MUST verify Stripe signature using `stripe-signature` header**
   - Uses `stripe.Webhook.construct_event()` for verification
   - Handles: `checkout.session.completed`, `customer.subscription.updated`, `customer.subscription.deleted`
   - Signature verification prevents fake payment events

4. **Usage Tracking:**
   - Background job: count webhooks per app each day
   - Store in `usage_history` table
   - Check limits on webhook receive
   - Alert user at 80% of limit

5. **Feature Flags by Plan:**
   ```python
   def can_use_feature(app: App, feature: str) -> bool:
       limits = {
           PlanTier.FREE: {"retention_hours": 24, "destinations": 3},
           PlanTier.PRO: {"retention_hours": 720, "destinations": 20},
           PlanTier.TEAM: {"retention_hours": 2160, "destinations": -1},  # unlimited
           PlanTier.ENTERPRISE: {"retention_hours": 8760, "destinations": -1},
       }
       limit = limits.get(app.plan_tier, limits[PlanTier.FREE])[feature]
       return limit == -1 or get_current_usage(app, feature) < limit
   ```

---

## Data Model Additions

### New Tables

**`usage_history`**
```sql
CREATE TABLE usage_history (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  app_id UUID REFERENCES apps(id) ON DELETE CASCADE,
  period DATE NOT NULL,  -- YYYY-MM
  webhook_count INTEGER DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(app_id, period)
);
CREATE INDEX idx_usage_history_app_period ON usage_history(app_id, period DESC);
```

**`subscriptions` (if using Stripe)**
```sql
CREATE TABLE subscriptions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  stripe_customer_id VARCHAR(255) UNIQUE,
  stripe_subscription_id VARCHAR(255) UNIQUE,
  stripe_price_id VARCHAR(255),
  status VARCHAR(50) NOT NULL,  -- active, canceled, past_due, trialing
  current_period_start TIMESTAMPTZ,
  current_period_end TIMESTAMPTZ,
  cancel_at_period_end BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_subscriptions_user ON subscriptions(user_id);
CREATE INDEX idx_subscriptions_status ON subscriptions(status);
```

### Database Migrations

**Strategy:** Use Alembic for all schema changes

**Prerequisite:** Alembic must be initialized in the project before migrations:
```bash
cd backend
pip install alembic
alembic init alembic
# Edit alembic.ini to set database URL
# Edit alembic/env.py to use SQLAlchemy AsyncSession
```

**Commands:**
```bash
# Create migration
alembic revision --autogenerate -m "Add usage_history and subscriptions"

# Apply migration
alembic upgrade head

# Rollback if needed
alembic downgrade -1
```

**Note:** PostgreSQL is required for analytics features (uses date_trunc, JSONB).

---

## Environment Variables

### New Environment Variables Required

```bash
# Analytics
ANALYTICS_RETENTION_DAYS=90

# SSE (Server-Sent Events)
REDIS_URL=redis://localhost:6379/0  # Required for SSE pub/sub in production

# Email Integration
SENDGRID_API_KEY=SG.xxx
SES_AWS_ACCESS_KEY_ID=xxx
SES_AWS_SECRET_ACCESS_KEY=xxx
SES_REGION=us-east-1
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=xxx
SMTP_PASSWORD=xxx

# Notion
NOTION_API_KEY=xxx

# Airtable (no global key - per destination)

# Google Sheets
GOOGLE_CLOUD_CREDENTIALS_PATH=/path/to/credentials.json

# Clerk Authentication
CLERK_SECRET_KEY=sk_test_xxx
CLERK_PUBLISHABLE_KEY=pk_test_xxx

# Stripe Billing
STRIPE_SECRET_KEY=sk_test_xxx
STRIPE_WEBHOOK_SECRET=whsec_xxx  # For webhook signature verification
STRIPE_PRICE_ID_PRO=price_xxx
STRIPE_PRICE_ID_TEAM=price_xxx

# Encryption (for sensitive credentials in destinations)
ENCRYPTION_KEY=xxx  # 32-byte URL-safe base64-encoded key
```

---

## Testing Strategy

### Phase 2 Testing
- **Unit Tests:** AnalyticsService queries, API key generation/hashing
- **Integration Tests:** Analytics API endpoint, SSE connection lifecycle
- **E2E Tests:** Dashboard page loads, webhook table pagination, replay button works
- **Target:** 80% code coverage for new code

### Phase 3 Testing
- **Unit Tests:** Each integration's delivery method with mocked clients
- **Integration Tests:** Real API calls to test environments where possible
- **E2E Tests:** Create destination → send webhook → verify delivery in external system

### Phase 5 Testing
- **Unit Tests:** Plan tier validation, usage limit checking
- **Integration Tests:** Stripe checkout flow (test mode), Clerk auth callbacks
- **E2E Tests:** Sign up → upgrade plan → verify feature access

---

## Rate Limiting & Performance

### Rate Limiting Strategy
- Dashboard endpoints: 60 requests/minute per user
- Analytics API: 30 requests/minute per app
- SSE connections: 5 concurrent connections per user
- Webhook receive: Per-app monthly limit (existing)

### Performance Notes
- Use database indexes on frequently queried columns
- Pagination cursor-based for large datasets (offset-based for Phase 2, cursor for later)
- Analytics queries use materialized views for heavy aggregations
- SSE connection pooling for efficiency

---

## Deployment & Infrastructure

### Production Requirements
- Redis required for SSE pub/sub (in-memory broadcaster dev-only)
- SSL/TLS required for all webhook endpoints
- Database connection pooling (SQLAlchemy pool)
- Background workers run as separate processes (Celery or asyncio tasks)
- Monitoring: Sentry for errors, DataDog/statsd for metrics

### Docker Updates
```yaml
# docker-compose.yml additions
services:
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

  worker:
    build: ./backend
    command: uvicorn hookflow.workers.delivery_worker:app --no-server
    depends_on: [redis, postgres]
```

---

## Implementation Priority

**Prerequisites:**
- Initialize Alembic for database migrations
- Create backend/hookflow/scripts directory for migration scripts
- Create backend/hookflow/api/dependencies.py for auth middleware

**Phase 2:**
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
- [ ] User can replay failed webhooks (endpoint exists, add UI)
- [ ] Real-time delivery updates visible on dashboard
- [ ] API keys can be created/revoked
- [ ] Analytics show delivery rates and trends
- [ ] All new code has 80%+ test coverage

### Phase 3
- [ ] Webhooks can be stored to database
- [ ] Webhooks can be sent via email
- [ ] Webhooks can create Notion pages
- [ ] Webhooks can create Airtable records
- [ ] Webhooks can append to Google Sheets
- [ ] All integrations follow same retry/error pattern

### Phase 5
- [ ] Users can sign up/login via Clerk
- [ ] Users see only their own apps
- [ ] Users can upgrade to paid plans via Stripe
- [ ] Usage limits are enforced
- [ ] Webhooks are blocked when limit exceeded
- [ ] Stripe webhooks verify signature

---

## Notes

- Existing codebase uses FastAPI + SQLAlchemy + Next.js 14 + Tailwind
- Queue system: Redis (production) / in-memory (dev)
- All new endpoints need proper error handling
- Frontend should use existing UI component library (shadcn/ui)
- Follow existing code patterns and conventions
- Webhook receive endpoint: `/api/v1/webhook/{app_id}` (public URL)
- Management API endpoints: `/api/v1/...` (protected after Phase 5)
- **Timezone handling:** Use `datetime.now(timezone.utc)` for all new code
- **Phase 2 Auth:** Dashboard is unauthenticated during Phase 2. Basic auth placeholder
  or demo mode. Full multi-tenant auth comes in Phase 5 with Clerk.
