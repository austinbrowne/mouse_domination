# Comprehensive UX & Feature Improvement Brainstorm

**Date:** 2026-01-25
**Status:** Ready for Planning
**Scope:** Application-wide UX overhaul + new features

---

## What We're Building

A unified, connected experience for Mouse Domination that transforms it from a collection of features into a cohesive creator business management platform. The goal is to make the app feel like one integrated system rather than separate modules.

### Core Problems Being Solved

1. **Disconnected Features** - CRM, Pipeline, Inventory, Revenue, and Podcasts don't link together
2. **Overwhelming for New Users** - No clear starting point or guided experience
3. **Missing Big Picture View** - No dashboard showing overall business health
4. **Manual Connections** - Users must mentally track relationships between entities
5. **Productization Readiness** - Need clearer value proposition for potential external users

---

## Why This Approach

**Chosen: Unified Dashboard + Connected Workflows**

We're keeping all existing features while adding:
- A powerful home dashboard with smart prioritization
- Deep entity connections (Company → Inventory → Deals → Revenue)
- Unified navigation and consistent UX patterns

**Rejected alternatives:**
- *Podcast Hub Pivot* - Would abandon valuable CRM/financial features
- *Modular Workspaces* - Too complex architecturally, may fragment experience

---

## Key Decisions

### 1. Unified Dashboard

**What:** A new home page that surfaces actionable items across all modules

**Content (prioritized by urgency):**
- **Action Items & Deadlines**
  - Inventory items with approaching deadlines (review due, return date)
  - Pipeline deals needing follow-up
  - Episodes in draft status approaching scheduled date
  - Pending payments to invoice

- **Revenue & Financial Health**
  - Month-to-date revenue across all sources
  - Outstanding invoices
  - Revenue trend (vs. previous month)

- **Pipeline Activity**
  - Active deals by status
  - Recent wins/losses

- **Quick Actions**
  - Add inventory item
  - Log revenue
  - Create episode
  - Quick contact lookup

### 2. Entity Connections (Relationship Mapping)

**Priority connections to implement:**

| From | To | Value |
|------|-----|-------|
| Company | All inventory, deals, collabs, revenue | See full brand relationship at a glance |
| Inventory Item | Content links, sales, revenue | Track product lifecycle: receive → review → monetize |
| Contact | Deal history, communications | Full relationship timeline |

**Implementation approach:**
- Add "Related Items" sections to detail pages
- Clickable links between entities
- Consider a unified "Company Profile" view showing everything

### 3. New Features to Add

#### 3.1 Task/Reminder System
- Tied to deals, inventory, contacts
- Due dates with dashboard surfacing
- Email/notification reminders (future)
- "Follow up with [Contact] about [Deal]" patterns

#### 3.2 Reporting & Analytics
- Revenue by source (pie chart)
- Revenue over time (line chart)
- Deal conversion funnel
- Inventory throughput (received → reviewed → sold)
- Top brands by revenue

#### 3.3 Email Integration (Phase 2)
- Manual email logging initially
- Gmail/Outlook integration later
- Thread tracking per contact

### 4. Navigation & UX Improvements

**Current pain points:**
- Sidebar has many items, no clear hierarchy
- No global search
- Inconsistent page layouts across modules

**Improvements:**
- Group navigation: CRM (Contacts, Companies), Content (Podcasts, Inventory), Money (Revenue, Pipeline, Affiliates)
- Add global search (Cmd+K pattern)
- Consistent page templates: list view, detail view, form view
- Breadcrumbs for deep navigation

### 5. Onboarding Flow (for productization)

- Welcome modal on first login
- Guided setup: "What do you want to track?"
- Progressive feature introduction
- Sample data option for exploration

---

## Implementation Phases

### Phase 1: Foundation (Dashboard + Navigation)
- Build unified dashboard
- Reorganize navigation with grouping
- Add global search

### Phase 2: Entity Connections
- Company profile view with related items
- Inventory → Content → Revenue linking
- Contact relationship timeline

### Phase 3: Task System
- Task model and CRUD
- Dashboard integration
- Due date tracking

### Phase 4: Reporting
- Revenue analytics
- Pipeline funnel
- Basic charts (Chart.js or similar)

### Phase 5: Polish & Onboarding
- Consistent UX patterns across all modules
- New user onboarding flow
- Email integration (if time permits)

---

## Open Questions

1. **Global Search Scope** - Search all entities or just commonly accessed ones?
2. **Task Notifications** - Email reminders, or in-app only initially?
3. **Chart Library** - Chart.js (simple) vs. something more advanced?
4. **Mobile Responsiveness** - Priority level for mobile UX improvements?

---

## Success Metrics

- Reduced clicks to complete common workflows
- Users can answer "how is my business doing?" from dashboard
- New users understand the app within 5 minutes
- All entities feel connected, not siloed

---

## Next Steps

Run `/workflows:plan` to create detailed implementation plan for Phase 1 (Dashboard + Navigation).
