# Product Requirements Document (PRD)

## Document Info

| Field | Value |
|-------|-------|
| **Title** | Mouse Domination: Creator Toolkit Enhancement Roadmap |
| **Author** | Claude + Austin |
| **Date** | 2026-01-12 |
| **Status** | `READY_FOR_REVIEW` |
| **Priority** | `High` |
| **Type** | `Enhancement` / `Roadmap` |

---

## 0. Exploration Summary

**Market Research Conducted:**
- Podcast planning tools (Milanote, Notion, Trello, Podsqueeze, Descript)
- Creator business management (InfluenceFlow, Upfluence, Aspire, Impact.com)
- YouTube creator tools (BrandConnect, ThoughtLeaders)
- CRM solutions for affiliates (Pipedrive, HubSpot)

**Existing System Analysis:**
- Current modules: Contacts, Companies, Inventory, Episode Guides, Affiliates, Pipeline, Collaborations, Templates
- Tech stack: Flask, SQLAlchemy, SQLite, Tailwind CSS, Alpine.js
- Auth: Cloudflare Access with Flask-Login
- Recent additions: Episode Guide Templates, Custom Options, Config-driven branding

**Competitive Positioning:**
Mouse Domination is unique in combining CRM + inventory tracking + episode planning + live show mode in one tool. Competitors typically focus on one area and charge $15-50/month for partial solutions.

**Constraints Found:**
- SQLite database (single-file, no concurrent writes at scale)
- Self-hosted on local machine via Cloudflare Tunnel
- Single-user focused (multi-user added recently but not primary use case)

---

## 1. Problem

**What's the problem?**
Content creators managing review units, sponsorships, and episode planning use 3-5 separate tools (spreadsheets, Notion, CRMs, calendar apps). This fragmentation leads to missed deadlines, lost sponsorship opportunities, and inefficient workflows. Mouse Domination already consolidates some of this, but lacks features that would make it a complete creator business toolkit.

**Who's affected?**
- Primary: Tech YouTubers and podcasters who receive review units
- Secondary: Any content creator managing brand relationships and recurring content

**Evidence:**
- Market research shows creators spend $100-300/month on fragmented tools (InfluenceFlow 2026 Guide)
- YouTube sponsorships surged 54% YoY in 2025 (Axios), indicating growing need for management tools
- No existing tool combines inventory tracking + episode planning + CRM + financial tracking

---

## 2. Goals

**Goals:**
1. Provide complete creator business management in one self-hosted tool
2. Reduce time spent on administrative tasks (sponsor outreach, tracking payments, planning episodes)
3. Enable creators to present professional media kits to potential sponsors
4. Improve visibility into business health (revenue, pipeline, deadlines)

**Non-Goals (out of scope):**
1. Multi-tenant SaaS deployment (this is personal tooling)
2. AI-generated content (show notes, thumbnails) - defer to specialized tools
3. Social media posting/scheduling
4. Video editing or production features
5. Podcast hosting or distribution

**Success Metric:**
| Metric | Baseline | Target |
|--------|----------|--------|
| Time to prepare episode guide | Manual | Template-driven (done) |
| Sponsor outreach tracking | Spreadsheet | Integrated pipeline |
| Payment visibility | None | Dashboard with status |
| Media kit generation | Manual | One-click export |

---

## 3. Solution

**Overview:**
Enhance Mouse Domination with four major feature sets: (1) Media Kit Generator for professional sponsor pitches, (2) Calendar View for deadline visualization, (3) Financial Tracking for payment management, and (4) Analytics Integration for automatic stats population. These build on the existing CRM, inventory, and episode guide foundation.

**Key Features:**

| Feature | Description | Priority |
|---------|-------------|----------|
| Media Kit Generator | Export PDF/HTML with channel stats, past sponsors, rates | `Must Have` |
| Calendar View | Visualize episodes, deadlines, review unit returns | `Must Have` |
| Financial Tracking | Payment status on deals, revenue dashboard | `Must Have` |
| Contract Storage | Attach PDFs to collaborations/deals | `Should Have` |
| Email Templates | Outreach templates with merge fields, copy-to-clipboard | `Should Have` |
| Analytics Import | Pull YouTube/podcast stats via API | `Nice to Have` |
| Multi-platform Calendar | Track content across YouTube, TikTok, podcast | `Nice to Have` |

---

## 4. Technical Approach

### Phase 4: Media Kit Generator

**Architecture:**
```
User clicks "Generate Media Kit"
    → Aggregates data from: Companies (past sponsors), Pipeline (rates),
      Affiliates (revenue), config (channel info)
    → Renders HTML template
    → Option to export as PDF (weasyprint) or shareable link
```

**New/Modified Files:**
| File | Changes |
|------|---------|
| `models.py` | Add `CreatorProfile` model (channel name, bio, social links, rates) |
| `routes/media_kit.py` | New blueprint for media kit CRUD and generation |
| `templates/media_kit/` | `profile_form.html`, `preview.html`, `public.html` |
| `services/pdf_generator.py` | PDF export using weasyprint |

**New Endpoints:**
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/media-kit` | View/edit creator profile |
| `POST` | `/media-kit` | Save creator profile |
| `GET` | `/media-kit/preview` | Preview media kit |
| `GET` | `/media-kit/export/pdf` | Download as PDF |
| `GET` | `/media-kit/public/<token>` | Public shareable link |

**Dependencies:**
- `weasyprint` - PDF generation from HTML/CSS

---

### Phase 5: Calendar View

**Architecture:**
```
Calendar fetches events from multiple sources:
    → Episode Guides (scheduled_date, recording date)
    → Pipeline deals (expected_close_date, deliverable_date)
    → Inventory (return_by_date for review units)
    → Collaborations (deadline)

Frontend: FullCalendar.js or simple custom grid
```

**New/Modified Files:**
| File | Changes |
|------|---------|
| `models.py` | Add `scheduled_date` to EpisodeGuide, `return_by_date` to InventoryItem, `deliverable_date` to SalesPipeline |
| `routes/calendar.py` | New blueprint for calendar view and event API |
| `templates/calendar/` | `view.html` with calendar component |

**New Endpoints:**
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/calendar` | Calendar view page |
| `GET` | `/api/calendar/events` | JSON events for date range |

**Dependencies:**
- None required (can use vanilla JS or Alpine.js for simple calendar)
- Optional: `FullCalendar` (JS library, no backend dependency)

---

### Phase 6: Financial Tracking

**Architecture:**
```
Extend Pipeline with payment tracking:
    → Add payment_status, payment_date, invoice_number fields
    → Dashboard aggregates: expected revenue, received, outstanding

Revenue sources:
    → Pipeline deals (sponsorships)
    → Affiliates (commission tracking already exists)
```

**New/Modified Files:**
| File | Changes |
|------|---------|
| `models.py` | Add payment fields to `SalesPipeline` |
| `routes/pipeline.py` | Add payment tracking UI |
| `routes/dashboard.py` | New financial dashboard or extend main dashboard |
| `templates/dashboard/financial.html` | Revenue charts, payment status |

**New Endpoints:**
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/dashboard/financial` | Financial overview |
| `POST` | `/pipeline/<id>/payment` | Update payment status |

**Dependencies:**
- None (use existing charting or simple HTML tables)

---

### Phase 7: Contract Storage & Email Templates

**Contract Storage:**
```
Add file upload capability to Collaborations and Pipeline
    → Store in /uploads/contracts/
    → Link files to deals
    → Track signed vs pending status
```

**Email Templates Enhancement:**
```
Extend existing Templates module:
    → Add merge field support: {{company_name}}, {{contact_name}}, {{rate}}
    → Copy-to-clipboard with merged values
    → Optional: mailto: link generation
```

**New/Modified Files:**
| File | Changes |
|------|---------|
| `models.py` | Add `Contract` model with file path, status |
| `routes/collabs.py`, `routes/pipeline.py` | File upload handling |
| `routes/templates.py` | Merge field rendering |
| `templates/templates/compose.html` | Template preview with merge |

---

## 5. Implementation Plan

### Phase 4: Media Kit Generator — 6-8 hours

**Deliverables:**
- CreatorProfile model and form
- Media kit preview page
- PDF export functionality
- Public shareable link with token

**Acceptance Criteria:**
- [ ] User can enter channel name, bio, social links, rate card
- [ ] Preview shows aggregated stats (subscriber count manual entry initially)
- [ ] Past sponsors pulled from Companies with `is_sponsor=True`
- [ ] PDF downloads with professional formatting
- [ ] Public link works without authentication
- [ ] Tests cover profile CRUD and PDF generation

---

### Phase 5: Calendar View — 4-6 hours

**Deliverables:**
- Calendar page with month/week view
- Events from Episode Guides, Pipeline, Inventory
- Click event to navigate to source record
- Color coding by event type

**Acceptance Criteria:**
- [ ] Calendar displays events from all sources
- [ ] Events link to their source records
- [ ] Month navigation works
- [ ] New date fields added to relevant models
- [ ] Migration script for new columns
- [ ] Tests cover event aggregation API

---

### Phase 6: Financial Tracking — 4-5 hours

**Deliverables:**
- Payment status fields on Pipeline
- Financial dashboard with revenue summary
- Payment update UI

**Acceptance Criteria:**
- [ ] Pipeline deals show payment status (pending, invoiced, paid, overdue)
- [ ] Dashboard shows: expected revenue, received, outstanding
- [ ] Revenue breakdown by month/quarter
- [ ] Affiliate revenue included in totals
- [ ] Tests cover payment status updates

---

### Phase 7: Contracts & Email Enhancement — 4-5 hours

**Deliverables:**
- File upload for contracts on Collabs/Pipeline
- Contract status tracking (draft, sent, signed)
- Email template merge fields
- Copy-to-clipboard with merged values

**Acceptance Criteria:**
- [ ] Can upload PDF/image contracts to deals
- [ ] Contract status visible in deal list
- [ ] Templates support {{company_name}}, {{contact_name}}, {{rate}} merge fields
- [ ] Preview shows merged output
- [ ] Copy button works with merged content
- [ ] Tests cover file upload and template rendering

---

**Total Effort:** 18-24 hours (across 4 phases)

---

## Test Strategy

| Test Type | What to Test | Coverage Target |
|-----------|--------------|-----------------|
| **Unit** | PDF generation, merge field parsing, event aggregation | >80% |
| **Integration** | Media kit export flow, calendar API, payment updates | Critical paths |
| **E2E** | Full media kit generation, calendar navigation | Happy path |
| **Security** | File upload validation, public link tokens | OWASP checklist |

---

## 6. Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| PDF generation issues on different OS | Medium | Medium | Use weasyprint with fallback to HTML-only |
| File upload security (malicious files) | Medium | High | Validate file types, scan with ClamAV optional |
| Calendar performance with many events | Low | Low | Paginate/limit events per query |
| Scope creep on "nice to have" features | Medium | Medium | Strict phase boundaries, defer analytics import |

---

## Security Review

**This feature involves:**
- [x] File uploads (contracts)
- [x] User input processing (profile, templates)
- [x] Database queries with user input

**Security measures required:**
- Validate file uploads (PDF, images only, size limits)
- Sanitize merge field inputs
- Token-based auth for public media kit links
- Rate limiting on public endpoints

**Flag:** `SECURITY_SENSITIVE` for Phase 7 (file uploads)

---

## 7. Open Questions

| Question | Owner | Status |
|----------|-------|--------|
| Should media kit include actual YouTube stats or manual entry? | Austin | `Open` |
| Preferred calendar library (FullCalendar vs custom)? | Austin | `Open` |
| Store contracts in DB (blob) or filesystem? | Claude | `Resolved` - Filesystem recommended |
| Include invoice generation in financial tracking? | Austin | `Open` |

---

## 8. Future Considerations

*Out of scope for this version, but worth noting:*
- YouTube API integration for automatic subscriber/view stats
- Podcast analytics import (Spotify, Apple Podcasts)
- Invoice PDF generation
- Email sending (SMTP integration)
- AI-powered show notes suggestions
- Mobile app or PWA

---

## 9. Architecture Decision Records

**ADRs to create if approved:**
- ADR: PDF generation library choice (weasyprint vs reportlab vs browser-based)
- ADR: File storage strategy (filesystem vs cloud vs database)

---

## 10. Rollback Plan

**Each phase is independent and can be rolled back separately:**

**Code rollback:**
- [ ] Each phase is a separate commit/PR
- [ ] `git revert [commit]` for any problematic phase
- [ ] Feature flags not needed (features are additive)

**Database rollback:**
- [ ] Migration down scripts for new columns
- [ ] New tables can be dropped without affecting existing data
- [ ] Backup before each phase deployment

---

## Approval

**Status:** `READY_FOR_REVIEW`

**Respond with:**
- `APPROVED_NEXT_PHASE` — Proceed to implementation (specify which phase)
- `REVISION_REQUESTED` — Specify changes needed
- `HALT_PENDING_DECISION` — Blocked on open questions

---

## Summary: Implementation Order

| Phase | Feature | Effort | Dependencies |
|-------|---------|--------|--------------|
| ~~1~~ | ~~Config-driven branding~~ | ~~Done~~ | - |
| ~~2~~ | ~~Custom Options~~ | ~~Done~~ | - |
| ~~3~~ | ~~Episode Guide Templates~~ | ~~Done~~ | - |
| **4** | **Media Kit Generator** | 6-8 hrs | None |
| **5** | **Calendar View** | 4-6 hrs | None |
| **6** | **Financial Tracking** | 4-5 hrs | None |
| **7** | **Contracts & Email** | 4-5 hrs | None |

Phases 4-7 are independent and can be implemented in any order based on priority.
