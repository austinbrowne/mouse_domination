# Episode Guide Enhancements - PRD

## Document Info

| Field | Value |
|-------|-------|
| **Title** | Episode Guide UX & Integration Enhancements |
| **Author** | Claude + Austin |
| **Date** | 2026-01-13 |
| **Status** | `READY_FOR_REVIEW` |
| **Priority** | `High` |
| **Type** | `Enhancement` |

---

## Overview

Enhance the Episode Guide feature with keyboard shortcuts, YouTube export, pause/resume timer, and guest/product linking. These improvements address UX gaps identified in competitor analysis and leverage Mouse Domination's unique CRM + Inventory integration.

**Total Estimated Effort:** 13 hours across 4 enhancements

---

## Enhancement 1: Keyboard Shortcuts for Live Mode

**Effort:** 2 hours | **Priority:** P1

### Problem
During live recording, hosts must click buttons to mark timestamps and control the timer. This breaks recording flow and requires looking away from content.

### Solution
Add keyboard shortcuts that work globally in live mode.

### Keyboard Mappings

| Shortcut | Action | Notes |
|----------|--------|-------|
| `Space` | Mark timestamp on focused/current item | Only when timer running |
| `S` | Start/Stop recording toggle | With confirmation for Stop |
| `↑` / `↓` | Navigate between items | Visual focus indicator |
| `D` | Toggle "discussed" on focused item | |
| `M` | Mark + advance to next item | Combo shortcut |
| `Esc` | Clear focus / close modals | |

### Technical Approach

**File:** `templates/episode_guide/live.html`

```javascript
// Add to episodeGuideLive() Alpine component
init() {
    this.fetchEvents();
    this.setupKeyboardShortcuts();
},

setupKeyboardShortcuts() {
    document.addEventListener('keydown', (e) => {
        // Ignore if typing in input/textarea
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

        switch(e.code) {
            case 'Space':
                e.preventDefault();
                if (this.isRecording && this.focusedItemId) {
                    this.markTimestamp(this.focusedItemId);
                }
                break;
            case 'KeyS':
                e.preventDefault();
                this.isRecording ? this.stopRecording() : this.startRecording();
                break;
            case 'ArrowUp':
                e.preventDefault();
                this.focusPreviousItem();
                break;
            case 'ArrowDown':
                e.preventDefault();
                this.focusNextItem();
                break;
            case 'KeyD':
                e.preventDefault();
                if (this.focusedItemId) this.toggleDiscussed(this.focusedItemId);
                break;
            case 'KeyM':
                e.preventDefault();
                if (this.isRecording && this.focusedItemId) {
                    this.markTimestamp(this.focusedItemId);
                    this.focusNextItem();
                }
                break;
            case 'Escape':
                this.focusedItemId = null;
                break;
        }
    });
},

focusedItemId: null,
focusNextItem() { /* Navigate to next undiscussed item */ },
focusPreviousItem() { /* Navigate to previous item */ },
```

**UI Changes:**
- Add `focusedItemId` state variable
- Visual focus ring on focused item (blue border)
- Keyboard shortcut hints in header tooltip
- Help icon showing shortcut reference

### Acceptance Criteria
- [ ] Space marks timestamp when timer running and item focused
- [ ] S toggles recording start/stop
- [ ] Arrow keys navigate between items with visual indicator
- [ ] D toggles discussed state
- [ ] M marks and advances (combo)
- [ ] Shortcuts disabled when typing in inputs
- [ ] Help tooltip shows available shortcuts

### Test Plan
- Unit: Test each shortcut handler function
- E2E: Manual test full recording flow with keyboard only

---

## Enhancement 2: YouTube Description Export

**Effort:** 2 hours | **Priority:** P1

### Problem
After recording, hosts manually format timestamps for YouTube descriptions. This takes 5-10 minutes and is error-prone.

### Solution
One-click "Copy for YouTube" button that generates formatted description with timestamps and links.

### Output Format

```
⏱️ TIMESTAMPS
00:00 Introduction
02:34 Logitech G Pro X Superlight 3
05:12 Razer DeathAdder V4
08:45 Community Questions
15:23 Keyboard News: Wooting 80HE
22:10 Personal Ramblings
45:23 Outro

🔗 LINKS MENTIONED
• Logitech G Pro X: https://example.com/gpro
• Razer DeathAdder: https://example.com/deathadder
• Wooting 80HE: https://example.com/wooting

📊 POLLS
Previous: Which grip style do you use? → https://poll.link/123
This Week: Best mouse sensor 2026? → https://poll.link/456

---
🎙️ Mousecast Episode #142 - January 13, 2026
```

### Technical Approach

**File:** `templates/episode_guide/view.html` (completed episodes)

```javascript
// Add to view page Alpine component
generateYouTubeDescription() {
    let output = '⏱️ TIMESTAMPS\n';

    // Sort items by timestamp
    const sortedItems = this.items
        .filter(i => i.timestamp_seconds !== null)
        .sort((a, b) => a.timestamp_seconds - b.timestamp_seconds);

    sortedItems.forEach(item => {
        output += `${this.formatTimestamp(item.timestamp_seconds)} ${item.title}\n`;
    });

    // Collect all links
    output += '\n🔗 LINKS MENTIONED\n';
    sortedItems.forEach(item => {
        if (item.links && item.links.length > 0) {
            item.links.forEach(link => {
                output += `• ${item.title}: ${link}\n`;
            });
        }
    });

    // Add polls if present
    if (this.previousPoll || this.newPoll) {
        output += '\n📊 POLLS\n';
        if (this.previousPoll) {
            output += `Previous: ${this.previousPoll}`;
            if (this.previousPollLink) output += ` → ${this.previousPollLink}`;
            output += '\n';
        }
        if (this.newPoll) {
            output += `This Week: ${this.newPoll}`;
            if (this.newPollLink) output += ` → ${this.newPollLink}`;
            output += '\n';
        }
    }

    // Footer
    output += `\n---\n🎙️ ${this.title} - Episode #${this.episodeNumber}`;

    return output;
},

copyToClipboard() {
    const text = this.generateYouTubeDescription();
    navigator.clipboard.writeText(text).then(() => {
        this.showCopiedNotification = true;
        setTimeout(() => this.showCopiedNotification = false, 2000);
    });
}
```

**UI Changes:**
- Add "Copy for YouTube" button on completed episode view
- Success notification "Copied to clipboard!"
- Optional: Preview modal showing formatted output

### Acceptance Criteria
- [ ] Button appears only on completed episodes (status='completed')
- [ ] Timestamps sorted chronologically
- [ ] Items without timestamps excluded from timestamp section
- [ ] Links collected and formatted
- [ ] Polls included when present
- [ ] Episode title and number in footer
- [ ] Clipboard copy works cross-browser
- [ ] Success notification displays

### Test Plan
- Unit: Test formatTimestamp function, generateYouTubeDescription output
- E2E: Copy output, paste in YouTube, verify formatting

---

## Enhancement 3: Pause/Resume Timer

**Effort:** 3 hours | **Priority:** P2

### Problem
If interrupted during recording (phone call, technical issue), hosts must either keep the timer running (inflating duration) or stop completely (losing ability to resume).

### Solution
Add Pause/Resume capability that tracks paused time separately.

### Technical Approach

**Model Changes:** `models.py`

```python
class EpisodeGuide(db.Model):
    # Existing fields...

    # New fields for pause tracking
    paused_at = db.Column(db.DateTime, nullable=True)  # When pause started
    total_paused_seconds = db.Column(db.Integer, default=0)  # Cumulative pause time
```

**State Machine:**

```
DRAFT → [Start] → RECORDING → [Pause] → PAUSED → [Resume] → RECORDING → [Stop] → COMPLETED
                      ↑                              ↓
                      └──────────────────────────────┘
```

**Route Changes:** `routes/episode_guide.py`

```python
@episode_guide_bp.route('/<int:id>/pause', methods=['POST'])
@login_required
def pause_recording(id):
    guide = EpisodeGuide.query.get_or_404(id)
    if guide.status != 'recording':
        return jsonify({'error': 'Not currently recording'}), 400

    guide.paused_at = datetime.now(timezone.utc)
    guide.status = 'paused'
    db.session.commit()

    return jsonify({'success': True, 'paused_at': guide.paused_at.isoformat()})

@episode_guide_bp.route('/<int:id>/resume', methods=['POST'])
@login_required
def resume_recording(id):
    guide = EpisodeGuide.query.get_or_404(id)
    if guide.status != 'paused':
        return jsonify({'error': 'Not currently paused'}), 400

    # Calculate pause duration and add to total
    pause_duration = (datetime.now(timezone.utc) - guide.paused_at).total_seconds()
    guide.total_paused_seconds = (guide.total_paused_seconds or 0) + int(pause_duration)
    guide.paused_at = None
    guide.status = 'recording'
    db.session.commit()

    return jsonify({'success': True, 'total_paused_seconds': guide.total_paused_seconds})
```

**Frontend Changes:** `templates/episode_guide/live.html`

```javascript
// Timer calculation adjustment
get elapsedSeconds() {
    if (!this.recordingStartedAt) return 0;

    let elapsed;
    if (this.isPaused) {
        // Use pause start time as endpoint
        elapsed = (new Date(this.pausedAt) - new Date(this.recordingStartedAt)) / 1000;
    } else {
        elapsed = (Date.now() - new Date(this.recordingStartedAt)) / 1000;
    }

    // Subtract cumulative paused time
    return Math.floor(elapsed - this.totalPausedSeconds);
}
```

**UI Changes:**
- Yellow "PAUSED" indicator (vs red "RECORDING")
- Pause button (shown when recording)
- Resume button (shown when paused)
- Display paused duration: "Paused: 2:34"

### Acceptance Criteria
- [ ] Pause button appears during recording
- [ ] Resume button appears when paused
- [ ] Timer stops counting during pause
- [ ] Paused time tracked in `total_paused_seconds`
- [ ] Final duration = total time - paused time
- [ ] Visual indicator changes (red → yellow)
- [ ] Timestamps still work correctly after resume
- [ ] Multiple pause/resume cycles accumulate correctly

### Database Migration

```sql
ALTER TABLE episode_guides ADD COLUMN paused_at DATETIME;
ALTER TABLE episode_guides ADD COLUMN total_paused_seconds INTEGER DEFAULT 0;
```

### Test Plan
- Unit: Test pause/resume routes, duration calculation
- Integration: Full recording with multiple pauses, verify final duration
- E2E: Manual pause/resume during recording

---

## Enhancement 4: Guest & Product Linking

**Effort:** 6 hours | **Priority:** P2

### Problem
Episodes often feature guests and review products, but there's no way to:
- Track which episodes a guest appeared on
- Link reviewed products to their episode appearances
- Generate "episodes featuring this product" lists

### Solution
Add many-to-many relationships between EpisodeGuide and Contact (guests) / Inventory (products).

### Technical Approach

**Model Changes:** `models.py`

```python
# Association tables
episode_guests = db.Table('episode_guests',
    db.Column('episode_id', db.Integer, db.ForeignKey('episode_guides.id'), primary_key=True),
    db.Column('contact_id', db.Integer, db.ForeignKey('contacts.id'), primary_key=True),
    db.Column('role', db.String(50), default='guest')  # guest, co-host, interview
)

episode_products = db.Table('episode_products',
    db.Column('episode_id', db.Integer, db.ForeignKey('episode_guides.id'), primary_key=True),
    db.Column('inventory_id', db.Integer, db.ForeignKey('inventory.id'), primary_key=True),
    db.Column('segment', db.String(50))  # Which segment featured this product
)

class EpisodeGuide(db.Model):
    # Existing fields...

    # New relationships
    guests = db.relationship('Contact', secondary=episode_guests,
                            backref=db.backref('episodes', lazy='dynamic'))
    featured_products = db.relationship('Inventory', secondary=episode_products,
                                        backref=db.backref('episodes', lazy='dynamic'))
```

**Route Changes:** `routes/episode_guide.py`

```python
@episode_guide_bp.route('/<int:id>/guests', methods=['POST'])
@login_required
def add_guest(id):
    guide = EpisodeGuide.query.get_or_404(id)
    contact_id = request.json.get('contact_id')
    role = request.json.get('role', 'guest')

    contact = Contact.query.get_or_404(contact_id)
    if contact not in guide.guests:
        guide.guests.append(contact)
        db.session.commit()

    return jsonify({'success': True, 'guest': contact.to_dict()})

@episode_guide_bp.route('/<int:id>/guests/<int:contact_id>', methods=['DELETE'])
@login_required
def remove_guest(id, contact_id):
    guide = EpisodeGuide.query.get_or_404(id)
    contact = Contact.query.get_or_404(contact_id)

    if contact in guide.guests:
        guide.guests.remove(contact)
        db.session.commit()

    return jsonify({'success': True})

# Similar routes for products: add_product, remove_product
```

**UI Changes - Edit Page:** `templates/episode_guide/edit.html`

```html
<!-- Guests Section -->
<div class="border-t pt-4 mt-4">
    <h3 class="font-semibold mb-2">Guests</h3>
    <div class="flex flex-wrap gap-2 mb-2">
        <template x-for="guest in guests" :key="guest.id">
            <span class="inline-flex items-center gap-1 px-3 py-1 bg-primary-100 text-primary-800 rounded-full">
                <span x-text="guest.name"></span>
                <button @click="removeGuest(guest.id)" class="hover:text-red-600">×</button>
            </span>
        </template>
    </div>
    <button @click="showGuestSearch = true" class="text-sm text-primary-600 hover:underline">
        + Add Guest
    </button>
</div>

<!-- Featured Products Section -->
<div class="border-t pt-4 mt-4">
    <h3 class="font-semibold mb-2">Featured Products</h3>
    <div class="flex flex-wrap gap-2 mb-2">
        <template x-for="product in featuredProducts" :key="product.id">
            <span class="inline-flex items-center gap-1 px-3 py-1 bg-green-100 text-green-800 rounded-full">
                <span x-text="product.product_name"></span>
                <button @click="removeProduct(product.id)" class="hover:text-red-600">×</button>
            </span>
        </template>
    </div>
    <button @click="showProductSearch = true" class="text-sm text-green-600 hover:underline">
        + Add Product
    </button>
</div>

<!-- Search Modal for Contacts -->
<div x-show="showGuestSearch" class="fixed inset-0 bg-black/50 flex items-center justify-center">
    <div class="bg-white rounded-lg p-4 w-96">
        <input type="text" x-model="guestSearchQuery" @input="searchGuests()"
               placeholder="Search contacts..." class="w-full border rounded px-3 py-2 mb-2">
        <div class="max-h-60 overflow-y-auto">
            <template x-for="contact in guestSearchResults" :key="contact.id">
                <button @click="addGuest(contact.id)"
                        class="w-full text-left px-3 py-2 hover:bg-gray-100 rounded">
                    <span x-text="contact.name"></span>
                    <span class="text-sm text-gray-500" x-text="contact.company?.name"></span>
                </button>
            </template>
        </div>
        <button @click="showGuestSearch = false" class="mt-2 text-gray-500">Cancel</button>
    </div>
</div>
```

**Search API:** `routes/contacts.py`

```python
@contacts_bp.route('/api/search')
@login_required
def search_contacts():
    q = request.args.get('q', '')
    contacts = Contact.query.filter(Contact.name.ilike(f'%{q}%')).limit(10).all()
    return jsonify([c.to_dict() for c in contacts])
```

**Display on Contact/Inventory Pages:**

On Contact detail page, show "Episodes Appeared In":
```html
<div class="mt-4">
    <h3>Episodes</h3>
    <ul>
        {% for episode in contact.episodes %}
        <li><a href="{{ url_for('episode_guide.view_guide', id=episode.id) }}">
            #{{ episode.episode_number }}: {{ episode.title }}
        </a></li>
        {% endfor %}
    </ul>
</div>
```

### Database Migration

```sql
CREATE TABLE episode_guests (
    episode_id INTEGER NOT NULL,
    contact_id INTEGER NOT NULL,
    role VARCHAR(50) DEFAULT 'guest',
    PRIMARY KEY (episode_id, contact_id),
    FOREIGN KEY (episode_id) REFERENCES episode_guides(id),
    FOREIGN KEY (contact_id) REFERENCES contacts(id)
);

CREATE TABLE episode_products (
    episode_id INTEGER NOT NULL,
    inventory_id INTEGER NOT NULL,
    segment VARCHAR(50),
    PRIMARY KEY (episode_id, inventory_id),
    FOREIGN KEY (episode_id) REFERENCES episode_guides(id),
    FOREIGN KEY (inventory_id) REFERENCES inventory(id)
);
```

### Acceptance Criteria
- [ ] Can add guests from Contact search
- [ ] Can add products from Inventory search
- [ ] Guests/products display as tags on episode edit page
- [ ] Can remove guests/products
- [ ] Contact page shows episodes they appeared in
- [ ] Inventory item page shows episodes it was featured in
- [ ] Episode view page shows guests and products
- [ ] Many-to-many relationship works correctly

### Test Plan
- Unit: Test add/remove guest/product routes
- Integration: Create episode, add guest, verify backref on Contact
- E2E: Full workflow adding guests and products to episode

---

## Implementation Order

| Phase | Enhancement | Effort | Dependencies |
|-------|-------------|--------|--------------|
| **1** | Keyboard Shortcuts | 2 hrs | None |
| **2** | YouTube Description Export | 2 hrs | None |
| **3** | Pause/Resume Timer | 3 hrs | DB migration |
| **4** | Guest & Product Linking | 6 hrs | DB migration, search APIs |

Phases 1-2 are independent quick wins. Phase 3-4 require database migrations.

---

## Files to Modify/Create

| File | Changes |
|------|---------|
| `models.py` | Add pause fields, association tables, relationships |
| `routes/episode_guide.py` | Add pause/resume, guest/product routes |
| `routes/contacts.py` | Add search API |
| `routes/inventory.py` | Add search API |
| `templates/episode_guide/live.html` | Keyboard shortcuts, pause UI |
| `templates/episode_guide/view.html` | YouTube export button |
| `templates/episode_guide/edit.html` | Guest/product linking UI |
| `templates/contacts/view.html` | Episodes list |
| `templates/inventory/view.html` | Episodes list |
| `tests/test_episode_guide_*.py` | New tests |

---

## Verification Plan

### Phase 1 (Keyboard Shortcuts)
```bash
# Manual test
1. Open live mode for any episode
2. Press S to start recording
3. Arrow down to navigate items
4. Space to mark timestamp
5. D to toggle discussed
6. M to mark and advance
7. S to stop recording
```

### Phase 2 (YouTube Export)
```bash
# Manual test
1. View completed episode with timestamps
2. Click "Copy for YouTube"
3. Paste into text editor
4. Verify format matches spec
```

### Phase 3 (Pause/Resume)
```bash
pytest tests/test_episode_guide_routes.py -k "pause" -v

# Manual test
1. Start recording
2. Click Pause - verify timer stops, yellow indicator
3. Wait 30 seconds
4. Click Resume - verify timer continues
5. Stop recording - verify duration excludes paused time
```

### Phase 4 (Guest/Product Linking)
```bash
pytest tests/test_episode_guide_routes.py -k "guest" -v
pytest tests/test_episode_guide_routes.py -k "product" -v

# Manual test
1. Edit episode, click Add Guest
2. Search for contact, add
3. Verify tag appears
4. View Contact page - verify episode listed
5. Repeat for products
```

---

## Security Considerations

- Guest/product search APIs require `@login_required`
- Contact/Inventory IDs validated before linking
- CSRF protection on all POST/DELETE routes
- No sensitive data exposed in search results

---

## Approval

**Status:** `READY_FOR_REVIEW`

Which enhancement would you like to start with?
1. Keyboard Shortcuts (2 hrs)
2. YouTube Description Export (2 hrs)
3. Pause/Resume Timer (3 hrs)
4. Guest & Product Linking (6 hrs)
