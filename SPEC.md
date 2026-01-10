# Mouse Domination - Product Specification

## Overview

A custom web application for **dazztrazak** to manage and grow a gaming peripheral review empire. This tool centralizes contact management, inventory tracking, affiliate revenue, content planning, and sales operations.

---

## User Profile & Current Assets

| Asset | Details |
|-------|---------|
| **YouTube** | dazztrazak - 4,000 subscribers |
| **Podcast** | MouseCast (on ManPhalanges channel) - weekly video podcast |
| **Twitter** | ~1,200 followers |
| **Discord** | 600 members |
| **Co-host** | ManPhalanges (~1,200 Twitter followers) |
| **Reviewer Network** | ~10 connections, including Aimadapt (21k subs) |
| **Company Relationships** | 20+ affiliate codes/links |

### Current Revenue Streams

| Stream | Status |
|--------|--------|
| Affiliate sales | $100-200/month (2 companies drive most) |
| Review unit resale | Ad hoc (eBay, r/MouseMarket, Discord, local) |
| Paid reviews | Not yet (review units only) |
| Podcast ads | Not yet |

### Monthly Inflow

- **Review units received:** 10-15 per month (more than can be reviewed)

---

## Goals

### 12-Month Targets

- [ ] 10,000+ YouTube subscribers (2.5x growth)
- [ ] Monetize MouseCast with embedded ads/sponsorships
- [ ] Start charging new/unknown companies for reviews
- [ ] Establish relationships with: Lamzu, WLMouse, Vaxee, Zowie, Razer, Logitech, Letussai
- [ ] Systematize affiliate tracking to understand what drives revenue
- [ ] Streamline review unit inventory and resale

---

## Core Modules

### 1. Contacts CRM

Track all people in your network.

**Fields:**
- Name
- Role: `reviewer` | `company_rep` | `podcast_guest` | `other`
- Company (if applicable)
- Email
- Twitter handle
- Discord handle
- YouTube channel (if applicable)
- Relationship status: `cold` | `warm` | `active` | `close`
- Notes
- Last contact date
- Tags (e.g., "potential collab", "sponsor contact", "friend")

**Key Contacts to Pre-populate:**
- ManPhalanges (co-host)
- Aimadapt (21k sub connection)
- Your 10 reviewer connections
- Company reps from your 20+ affiliate relationships

---

### 2. Companies / Brands

Track every peripheral company and your relationship with them.

**Fields:**
- Company name
- Category: `mice` | `keyboards` | `mousepads` | `iems` | `other`
- Website
- Relationship status: `no_contact` | `reached_out` | `active` | `affiliate_only` | `past`
- Primary contact (link to Contact)
- Affiliate program: `yes` | `no` | `pending`
- Affiliate code/link
- Commission rate (%)
- Review units received (count)
- Total affiliate revenue (tracked over time)
- Notes
- Priority: `target` | `active` | `low` (for companies you want to get into)

**Target Companies to Track:**
- Lamzu
- WLMouse
- Vaxee
- Zowie
- Razer
- Logitech
- Letussai
- (Plus all 20+ you currently have relationships with)

---

### 3. Inventory (Review Units + Personal Purchases)

Track all products - both review units received and personal purchases.

**Fields:**
- Product name (Model)
- Company/Source (link to Company)
- Category: `mouse` | `keyboard` | `mousepad` | `iem` | `other`
- **Source type:** `review_unit` | `personal_purchase`
- Date acquired
- Cost (for personal purchases, $0 for review units)
- On Amazon: `yes` | `no`
- Deadline (optional - only for hard company deadlines)
- Status: `in_queue` | `reviewing` | `reviewed` | `keeping` | `listed` | `sold`
- Condition: `new` | `open_box` | `used`
- Notes

**Content Links (when reviewed):**
- Short URL (YouTube Short)
- Short publish date
- Video URL (full review)
- Video publish date

**Sales Tracking:**
- Sold: `yes` | `no`
- Sale price
- Fees (platform fees)
- Shipping cost
- P/L (auto-calculated: sale price - fees - shipping - cost)
- Marketplace: `ebay` | `reddit` | `discord` | `offerup` | `mercari` | `facebook` | `local` | `other`
- Buyer (name/username)
- Sale notes

**Dashboard Metrics:**
- Units in queue (not yet reviewed)
- Units available to sell
- Review units vs personal purchases breakdown
- Total revenue from unit sales this month/year
- Total P/L (profit/loss)
- Average sale price
- Upcoming deadlines

---

### 4. Content Tracker (Videos)

Track all YouTube videos.

**Fields:**
- Title
- URL
- Publish date
- Type: `review` | `comparison` | `guide` | `tierlist` | `other`
- Products featured (link to Inventory items)
- Company (primary)
- Affiliate links included: `yes` | `no`
- Sponsored: `yes` | `no`
- Views (manual update or future API integration)
- Notes

**Purpose:**
- See which videos likely drive affiliate revenue
- Track sponsored vs non-sponsored content ratio
- Identify top-performing content types

---

### 5. Podcast Episodes (MouseCast)

Track all podcast episodes.

**Fields:**
- Episode number
- Title
- Publish date
- YouTube URL
- Guests (link to Contacts)
- Topics / products discussed
- Sponsored: `yes` | `no`
- Sponsor (if applicable)
- Notes

**Purpose:**
- Track guest history (don't repeat too often, identify who to invite back)
- Pipeline for future guests
- Track when monetization starts

---

### 6. Affiliate Revenue Tracking

Track monthly revenue by company.

**Fields:**
- Month/Year
- Company (link to Company)
- Revenue amount
- Notes (e.g., "big video dropped this month")

**Dashboard Metrics:**
- Total revenue this month / this year
- Revenue by company (chart)
- Revenue trend over time
- Top performing companies

**Future Enhancement:**
- Link revenue spikes to specific videos

---

### 7. Collaborations & Outreach

Track cross-promos, guest appearances, and outreach.

**Fields:**
- Type: `guest_on_their_channel` | `guest_on_mousecast` | `cross_promo` | `collab_video`
- Contact (link to Contact)
- Status: `idea` | `reached_out` | `confirmed` | `completed` | `declined`
- Date (scheduled or completed)
- Their channel/platform
- Their audience size
- Result/notes (views, new subs, etc.)
- Follow-up needed: `yes` | `no`

**Purpose:**
- Systematically grow through collaborations
- Track who you've worked with
- Identify high-value collabs to repeat

---

### 8. Sales Pipeline (Future Paid Work)

Track potential and active sponsorship deals.

**Fields:**
- Company (link to Company)
- Contact (link to Contact)
- Type: `paid_review` | `podcast_ad` | `sponsored_segment` | `other`
- Status: `lead` | `negotiating` | `confirmed` | `completed` | `lost`
- Rate quoted
- Rate agreed
- Deliverables
- Deadline
- Payment status: `pending` | `invoiced` | `paid`
- Notes

**Purpose:**
- Track when you start charging
- Manage sponsor relationships professionally
- Know your rates and what you've charged

---

## Local Selling Channels

Based on research, here are recommended platforms for selling review units locally:

| Platform | Pros | Fees |
|----------|------|------|
| **OfferUp** | Verified users (TruYou), community meetup spots, 20M+ users | Free for local |
| **Mercari** | Easy to use, large user base | 2.9% + $0.50 |
| **Facebook Marketplace** | Huge reach, integrated messaging | Free |
| **Craigslist** | Free, no-frills, straightforward | Free |
| **Nextdoor** | Neighborhood trust, community-based | Free |
| **5miles** | Safety-focused, user verification | Free for local |

**Already Using:**
- eBay (good for shipping, wider reach)
- r/MouseMarket (enthusiast buyers, fair prices)
- Discord (600 members, warm audience)

---

## Tech Stack

| Component | Choice | Rationale |
|-----------|--------|-----------|
| **Backend** | Python + Flask | Simple, you can run with one command |
| **Database** | SQLite | Local file, no setup, portable |
| **Frontend** | HTML + Tailwind CSS + Alpine.js | Clean UI, minimal JavaScript complexity |
| **Hosting** | Local (localhost:5000) | Run on your machine, access from any device on same network |

**To Run:**
```bash
python app.py
# Open http://localhost:5000 in browser
```

**Mobile Access:**
- Find your computer's local IP (e.g., 192.168.1.100)
- Open http://192.168.1.100:5000 on phone (same WiFi)

---

## User Interface

### Navigation

Simple sidebar with sections:
- **Dashboard** (overview metrics)
- **Contacts**
- **Companies**
- **Inventory**
- **Videos**
- **Podcast**
- **Affiliates**
- **Collabs**
- **Sales Pipeline**

### Dashboard Widgets

1. **Quick Stats**
   - Total contacts
   - Active company relationships
   - Units in inventory (by status)
   - Affiliate revenue this month

2. **Action Items**
   - Units waiting to be reviewed
   - Units listed but not sold
   - Outreach needing follow-up
   - Upcoming deadlines

3. **Recent Activity**
   - Last 5 videos published
   - Last 5 units received
   - Last 5 sales

---

## Future Automations (Phase 2+)

These can be added after core app is working:

| Automation | Description |
|------------|-------------|
| **YouTube API Integration** | Auto-pull video stats, new video notifications |
| **Twitter Cross-Post** | Auto-tweet when new video publishes |
| **Affiliate Dashboard Sync** | If companies have APIs, pull revenue data |
| **Inventory Alerts** | Notify when queue is backing up |
| **Email Templates** | Quick outreach templates for sponsors, collabs |
| **Discord Bot** | Post new videos to your Discord automatically |

---

## Data Model Summary

```
Contacts
  └── linked to Companies (many-to-one)
  └── linked to Collabs (many-to-many)
  └── linked to Podcast Episodes as guests (many-to-many)

Companies
  └── linked to Contacts (one-to-many)
  └── linked to Inventory (one-to-many)
  └── linked to Videos (one-to-many)
  └── linked to Affiliate Revenue (one-to-many)
  └── linked to Sales Pipeline (one-to-many)

Inventory (Review Units)
  └── linked to Company (many-to-one)
  └── linked to Video (many-to-one, optional)

Videos
  └── linked to Company (many-to-one)
  └── linked to Inventory items featured (many-to-many)

Podcast Episodes
  └── linked to Guests/Contacts (many-to-many)

Affiliate Revenue
  └── linked to Company (many-to-one)

Collabs
  └── linked to Contact (many-to-one)

Sales Pipeline
  └── linked to Company (many-to-one)
  └── linked to Contact (many-to-one)
```

---

## Build Phases

### Phase 1: Core CRM & Inventory (MVP)
- [ ] Project setup (Flask app structure)
- [ ] Database models
- [ ] Contacts CRUD
- [ ] Companies CRUD
- [ ] Inventory CRUD
- [ ] Basic dashboard
- [ ] Mobile-responsive UI

### Phase 2: Content & Revenue Tracking
- [ ] Videos tracker
- [ ] Podcast episodes tracker
- [ ] Affiliate revenue tracking
- [ ] Dashboard charts

### Phase 3: Growth Tools
- [ ] Collaborations tracker
- [ ] Sales pipeline
- [ ] Outreach templates
- [ ] Follow-up reminders

### Phase 4: Automations
- [ ] YouTube API integration
- [ ] Twitter cross-posting
- [ ] Discord bot notifications
- [ ] Email automation

---

## Confirmed Decisions

| Decision | Choice |
|----------|--------|
| **Data Import** | Import existing spreadsheet (Mouse_Mastersheet.xlsx) |
| **Multi-user** | Single user for now, design for multi-user later |
| **Backups** | Daily auto-backup to JSON/CSV, Supabase-ready architecture |
| **Theme** | Clean, minimal, blue accent |
| **Giveaways** | Skip for now (can add later) |
| **Inventory** | Combined review units + personal purchases with source_type flag |
| **Deadlines** | Optional field, only used for hard company deadlines |

---

## Data Import Mapping

From `Mouse_Mastersheet.xlsx`:

| Spreadsheet Tab | → App Module |
|-----------------|--------------|
| Review Units | → Inventory (source_type: review_unit) |
| Purchased Mice | → Inventory (source_type: personal_purchase) |
| Affiliate Sales | → Companies (affiliate fields) |
| Giveaways | → Skip for now |
| Rakuten Dispute | → Ignore |

**Field Mapping (Review Units → Inventory):**
- Model → product_name
- Acquired Date → date_acquired
- Amazon? → on_amazon
- Deadline → deadline
- Done? → status (Y = reviewed)
- Short Date → short_publish_date
- Short → short_url
- Video Date → video_publish_date
- Video → video_url
- Category → category
- Source → company
- Sold? → sold
- Price → sale_price
- Fees → fees
- Shipping → shipping
- P/L → profit_loss (auto-calc)
- Marketplace → marketplace
- Buyer → buyer
- Notes/Notes 2 → notes

---

## Approval

✅ Spec reviewed and refined based on existing spreadsheet data.

Ready to build Phase 1.
