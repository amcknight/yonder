# Reserve Chart Category Coloring — Round 1 (Quick Color Preview) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Color reserve work by building system so a buyer scanning the timeline can read *what kind* of spending is coming — built as a low-risk visual preview on real data, plus a tested label→system classifier.

**Architecture:** Two parts. (1) A pure-Python `categorize(label) -> system` classifier backed by an ordered keyword table — the durable, tested core. (2) A self-contained HTML preview (`docs/mockups/reserve-bubbles.html`, copied from the existing `realdata-v4` sketch) that mirrors the same small keyword table in JS and applies category colors to the per-year bubbles (solid-dominant, with a donut for big multi-system years), the tap-to-open line-item list (swatch dots — the priority), and a category legend. The hardened canonical chart is **not** touched this round.

**Tech Stack:** Python 3.11+ / pydantic / pytest (classifier). Vanilla SVG + JS in a static HTML file (preview). `uv run pytest` for tests; `python -m http.server` to view the mock.

**Spec:** [docs/superpowers/specs/2026-06-06-reserve-chart-category-coloring-design.md](../specs/2026-06-06-reserve-chart-category-coloring-design.md)

---

## File Structure

- **Create:** `src/yonder/outlook/categories.py` — the 5 system-bucket names + ordered keyword table + `categorize(label)`. One responsibility: map a raw expenditure label to a system bucket.
- **Create:** `tests/test_outlook_categories.py` — unit tests for `categorize`, including the real Spectrum 4 labels.
- **Create:** `docs/mockups/reserve-bubbles.html` — the preview chart (copy of the `realdata-v4` bubble sketch + category coloring). Self-contained; hardcoded Spectrum 4 data, as the sketch already is.

Out of scope this round (Round 2): `category` field on `Expenditure`, extractor wiring, and folding the bubble view into the canonical chart.

---

## Task 1: System buckets + `categorize` (happy path)

**Files:**
- Create: `src/yonder/outlook/categories.py`
- Test: `tests/test_outlook_categories.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_outlook_categories.py
from yonder.outlook.categories import (
    SYSTEMS,
    categorize,
    ENVELOPE,
    MECHANICAL,
    PLUMBING_FIRE,
    ELECTRICAL_VERTICAL,
    AMENITIES_SITE,
)


def test_systems_is_the_five_buckets_in_priority_order():
    assert SYSTEMS == [
        ENVELOPE,
        MECHANICAL,
        PLUMBING_FIRE,
        ELECTRICAL_VERTICAL,
        AMENITIES_SITE,
    ]


def test_obvious_labels_map_to_expected_systems():
    assert categorize("Low-Slope Roof") == ENVELOPE
    assert categorize("Hot Water Tanks") == MECHANICAL
    assert categorize("Domestic Water Pipes") == PLUMBING_FIRE
    assert categorize("Elevator Modernization") == ELECTRICAL_VERTICAL
    assert categorize("Lobby") == AMENITIES_SITE


def test_unmatched_label_falls_back_to_amenities_site():
    assert categorize("Something Totally Unknown") == AMENITIES_SITE


def test_match_is_case_insensitive():
    assert categorize("low-slope ROOF") == ENVELOPE
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_outlook_categories.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'yonder.outlook.categories'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/yonder/outlook/categories.py
"""Map a raw reserve-expenditure label to one of five building-system buckets.

The mapping is deliberately small and keyword-driven; it is the single source of
truth for label -> system. The reserve-chart preview mirrors this keyword table
in JS, so keep the two in sync (see docs/mockups/reserve-bubbles.html).

Buckets are checked in SYSTEMS order, so that order also resolves ties when a
label contains keywords from more than one bucket.
"""

from __future__ import annotations

ENVELOPE = "Envelope"
MECHANICAL = "Mechanical"
PLUMBING_FIRE = "Plumbing & Fire"
ELECTRICAL_VERTICAL = "Electrical & Vertical"
AMENITIES_SITE = "Amenities & Site"

# Priority order: earlier buckets win ties. AMENITIES_SITE is also the fallback.
SYSTEMS = [ENVELOPE, MECHANICAL, PLUMBING_FIRE, ELECTRICAL_VERTICAL, AMENITIES_SITE]

# Lowercased substring keywords, checked in SYSTEMS order.
_KEYWORDS: dict[str, tuple[str, ...]] = {
    ENVELOPE: (
        "roof", "wall", "window", "membrane", "sealant", "guardrail",
        "balcony", "door", "paint", "coating", "waterproof", "deck",
        "entrance", "slab", "panel", "eyebrow",
    ),
    MECHANICAL: (
        "hvac", "boiler", "hot water", "tank", "cooling", "heat exchanger",
        "pump", "mechanical", "ventilation",
    ),
    PLUMBING_FIRE: (
        "pipe", "sprinkler", "fire", "drainage", "sump", "sewer",
        "plumbing", "gas",
    ),
    ELECTRICAL_VERTICAL: (
        "elevator", "lift", "generator", "power", "lighting",
        "electrical", "distribution",
    ),
    AMENITIES_SITE: (
        "lobby", "hallway", "common", "playground", "mailbox", "landscap",
        "softscap", "hardscap", "garden", "site", "signage", "compactor",
        "garbage", "amenity", "feature", "pool", "gym", "fitness",
    ),
}


def categorize(label: str) -> str:
    """Return the system bucket for an expenditure label.

    Falls back to AMENITIES_SITE when no keyword matches.
    """
    text = label.lower()
    for system in SYSTEMS:
        if any(kw in text for kw in _KEYWORDS[system]):
            return system
    return AMENITIES_SITE
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_outlook_categories.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add src/yonder/outlook/categories.py tests/test_outlook_categories.py
git commit -m "feat: add label->system reserve category classifier"
```

---

## Task 2: Pin the classifier against the real Spectrum 4 labels

This locks in the tie-break/priority behavior on the actual messy labels, so the colors on the preview are deterministic and we notice if a keyword edit regresses a real label.

**Files:**
- Modify: `tests/test_outlook_categories.py`
- Modify (only if a case fails): `src/yonder/outlook/categories.py`

- [ ] **Step 1: Write the failing/locking test**

Add to `tests/test_outlook_categories.py`:

```python
import pytest

# (label, expected system) for the real Spectrum 4 depreciation-report items.
SPECTRUM4_CASES = [
    ("Hot Water Tanks", MECHANICAL),
    ("Expansion Tanks", MECHANICAL),
    ("Reheat Tanks", MECHANICAL),
    ("HVAC Parkade", MECHANICAL),
    ("Balcony Membrane", ENVELOPE),
    ("Conc Eyebrow Membrane", ENVELOPE),
    ("Sealant", ENVELOPE),
    ("Paint Coating", ENVELOPE),
    ("Heat Exchanger", MECHANICAL),
    ("Lobby", AMENITIES_SITE),
    ("Hallways/Common", AMENITIES_SITE),
    ("HVAC Building", MECHANICAL),
    ("Misc Mechanical", MECHANICAL),
    ("Water Pumps", MECHANICAL),
    ("Garbage Compactor", AMENITIES_SITE),
    ("Playground", AMENITIES_SITE),
    ("Sliding Doors", ENVELOPE),
    ("Balcony Swing Doors", ENVELOPE),
    ("Front Entrance", ENVELOPE),
    ("Low-Slope Roof", ENVELOPE),
    ("Below-Grade Membrane", ENVELOPE),
    ("Garden Waterproofing", ENVELOPE),
    ("Balcony Guardrails", ENVELOPE),
    ("Roof Decks", ENVELOPE),
    ("Elevator Modernization", ELECTRICAL_VERTICAL),
    ("Elevator Cab", ELECTRICAL_VERTICAL),
    ("Domestic Water Pipes", PLUMBING_FIRE),
    ("Sprinkler/Fire", PLUMBING_FIRE),
    ("Cooling Tower", MECHANICAL),
    ("Service Distribution", ELECTRICAL_VERTICAL),
    ("Mailboxes", AMENITIES_SITE),
    ("Outdoor Lighting", ELECTRICAL_VERTICAL),
    ("Site Handrails", AMENITIES_SITE),
    ("Water Feature", AMENITIES_SITE),
    ("Emergency Generator", ELECTRICAL_VERTICAL),
    ("Entry Doors", ENVELOPE),
    ("Service Doors", ENVELOPE),
    ("Power Distribution", ELECTRICAL_VERTICAL),
    ("Softscaping", AMENITIES_SITE),
    ("Hardscaping", AMENITIES_SITE),
    ("Drainage", PLUMBING_FIRE),
    ("Conc Balcony Slabs", ENVELOPE),
    ("Ext Walls Concrete", ENVELOPE),
    ("Ext Walls Metal Panel", ENVELOPE),
    ("Window-wall", ENVELOPE),
    ("Interior Doors", ENVELOPE),
    ("Gas Pipes", PLUMBING_FIRE),
]


@pytest.mark.parametrize("label,expected", SPECTRUM4_CASES)
def test_spectrum4_labels_classify_deterministically(label, expected):
    assert categorize(label) == expected
```

- [ ] **Step 2: Run the tests**

Run: `uv run pytest tests/test_outlook_categories.py -v`
Expected: all 46 parametrized cases PASS with the Task 1 keyword table. If any case fails, the keyword table needs a targeted fix — go to Step 3; otherwise skip to Step 4.

- [ ] **Step 3: Fix only the failing keyword(s)**

If (and only if) a case fails, adjust `_KEYWORDS` in `src/yonder/outlook/categories.py` minimally to satisfy it without breaking the others, then re-run Step 2 until green. (Do not loosen a keyword to a bare word like `"water"` — that would mis-pull "Hot Water Tanks"/"Water Feature". Prefer specific phrases.)

- [ ] **Step 4: Commit**

```bash
git add tests/test_outlook_categories.py src/yonder/outlook/categories.py
git commit -m "test: pin reserve classifier against real Spectrum 4 labels"
```

---

## Task 3: Preview chart with solid-dominant colors + swatch-dot list + legend

Copy the existing bubble sketch and add coloring. The line chart, slider, bubble lane, and tap-to-expand box already exist in `realdata-v4.html`; this task only adds color.

**Files:**
- Create: `docs/mockups/reserve-bubbles.html` (start as a byte copy of `.superpowers/brainstorm/3720-1780644069/content/realdata-v4.html`)

- [ ] **Step 1: Copy the sketch to the mockups folder**

Run:
```bash
cp ".superpowers/brainstorm/3720-1780644069/content/realdata-v4.html" "docs/mockups/reserve-bubbles.html"
```
Expected: file exists at `docs/mockups/reserve-bubbles.html`.

- [ ] **Step 2: Add the JS category table + helpers (mirror of the Python classifier)**

In `docs/mockups/reserve-bubbles.html`, immediately after the line that defines the data array (`var EXP=[ ... ];` block, right before `var startBal=...`), insert:

```javascript
// Mirror of src/yonder/outlook/categories.py — keep in sync.
var SYS={ENV:'Envelope',MECH:'Mechanical',PLUMB:'Plumbing & Fire',ELEC:'Electrical & Vertical',AMEN:'Amenities & Site'};
var SYS_ORDER=[SYS.ENV,SYS.MECH,SYS.PLUMB,SYS.ELEC,SYS.AMEN];
var SYS_COLOR={};
SYS_COLOR[SYS.ENV]='#a78bfa';   // violet
SYS_COLOR[SYS.MECH]='#fb923c';  // orange (not amber)
SYS_COLOR[SYS.PLUMB]='#f472b6'; // rose/magenta
SYS_COLOR[SYS.ELEC]='#2dd4bf';  // teal (not cyan)
SYS_COLOR[SYS.AMEN]='#94a3b8';  // slate-gray (misc)
var SYS_KW={};
SYS_KW[SYS.ENV]=['roof','wall','window','membrane','sealant','guardrail','balcony','door','paint','coating','waterproof','deck','entrance','slab','panel','eyebrow'];
SYS_KW[SYS.MECH]=['hvac','boiler','hot water','tank','cooling','heat exchanger','pump','mechanical','ventilation'];
SYS_KW[SYS.PLUMB]=['pipe','sprinkler','fire','drainage','sump','sewer','plumbing','gas'];
SYS_KW[SYS.ELEC]=['elevator','lift','generator','power','lighting','electrical','distribution'];
SYS_KW[SYS.AMEN]=['lobby','hallway','common','playground','mailbox','landscap','softscap','hardscap','garden','site','signage','compactor','garbage','amenity','feature','pool','gym','fitness'];
function categorize(label){
  var t=String(label).toLowerCase();
  for(var i=0;i<SYS_ORDER.length;i++){ var s=SYS_ORDER[i];
    for(var j=0;j<SYS_KW[s].length;j++){ if(t.indexOf(SYS_KW[s][j])>=0) return s; } }
  return SYS.AMEN;
}
// Per-year {system: dollars}, then the dominant system for that year.
function yearSystems(y){ var m={}; (MAP[y]||[]).forEach(function(it){ var s=categorize(it.label); m[s]=(m[s]||0)+it.amt; }); return m; }
function dominantSystem(y){ var m=yearSystems(y), best=SYS.AMEN, bv=-1;
  SYS_ORDER.forEach(function(s){ if((m[s]||0)>bv){ bv=m[s]||0; best=s; } }); return best; }
```

- [ ] **Step 3: Color the year bubbles by dominant system**

In the bubble-drawing loop, find the `circle` for each year. In `realdata-v4.html` it reads (future years filled `#6366f1`, past years outlined):

```javascript
g.appendChild(el('circle',{cx:x,cy:laneY,r:r,fill:isPast?'none':'#6366f1',opacity:openY===y?0.95:(isPast?0.9:0.5),stroke:openY===y?'#a5b4fc':(isPast?'#6366f1':'none'),'stroke-width':isPast?1.3:1.5,'stroke-dasharray':isPast?'2 2':''}));
```

Replace it with a category-colored version (compute the color once just above this line):

```javascript
var dom=dominantSystem(y), dc=SYS_COLOR[dom];
g.appendChild(el('circle',{cx:x,cy:laneY,r:r,fill:isPast?'none':dc,opacity:openY===y?0.95:(isPast?0.9:0.55),stroke:openY===y?'#e2e8f0':(isPast?dc:'none'),'stroke-width':isPast?1.3:1.5,'stroke-dasharray':isPast?'2 2':''}));
```

- [ ] **Step 4: Add swatch dots to the expanded line-item list (the priority)**

In the `openY` expansion block, find the per-item label render:

```javascript
svg.appendChild(el('text',{x:bx+8,y:by+25+i*lh,'font-size':8.5,fill:'#cbd5e1'},"• "+it.label));
```

Replace the `"• "` bullet with a colored swatch circle, and shift the label text right to make room:

```javascript
var sc=SYS_COLOR[categorize(it.label)];
svg.appendChild(el('circle',{cx:bx+11,cy:by+25+i*lh-3,r:3,fill:sc}));
svg.appendChild(el('text',{x:bx+18,y:by+25+i*lh,'font-size':8.5,fill:'#cbd5e1'},it.label));
```

(The amount text on the right is unchanged.)

- [ ] **Step 5: Add the category legend row**

Find the existing legend `<div class="legend"> ... </div>` block in the HTML body. Immediately after its closing `</div>`, add a second legend row:

```html
<div class="legend" id="catLegend"></div>
```

Then, near the end of the `<script>` IIFE (just before the final `draw(0);` call), populate it from only the systems present in this building's data:

```javascript
(function buildCatLegend(){
  var present={}; BYEAR.forEach(function(y){ Object.keys(yearSystems(y)).forEach(function(s){ present[s]=true; }); });
  var box=document.getElementById('catLegend');
  SYS_ORDER.forEach(function(s){ if(!present[s]) return;
    var span=document.createElement('span');
    span.innerHTML='<i class="sw" style="background:'+SYS_COLOR[s]+'"></i> '+s;
    box.appendChild(span);
  });
})();
```

- [ ] **Step 6: Verify visually**

Run (from repo root):
```bash
python -m http.server 8000
```
Open `http://localhost:8000/docs/mockups/reserve-bubbles.html` and confirm:
- Bubbles are no longer all-indigo: e.g. 2037 reads **violet** (Envelope dominant), 2027 reads **orange/teal** per its mix.
- Tapping a year opens the list with a **colored dot** beside each line item (the priority).
- A second legend row shows only the systems that appear in the data, each with its color.
- No console errors.

- [ ] **Step 7: Commit**

```bash
git add docs/mockups/reserve-bubbles.html
git commit -m "feat: category-colored reserve bubble preview (dominant + swatch list)"
```

---

## Task 4: Donut markers for big multi-system years

Add the multicolor donut the user asked to try: big years whose spend spans multiple systems show 2–3 wedges; small or single-system years keep the solid dominant fill from Task 3.

**Files:**
- Modify: `docs/mockups/reserve-bubbles.html`

- [ ] **Step 1: Add a donut-wedge helper**

After the `dominantSystem` function added in Task 3 Step 2, add:

```javascript
// SVG arc path for a donut wedge from angle a0..a1 (radians), inner ri..outer ro.
function wedgePath(cx,cy,ri,ro,a0,a1){
  function P(r,a){ return [cx+r*Math.cos(a), cy+r*Math.sin(a)]; }
  var large=(a1-a0)>Math.PI?1:0;
  var o0=P(ro,a0), o1=P(ro,a1), i1=P(ri,a1), i0=P(ri,a0);
  return 'M'+o0[0]+' '+o0[1]+' A'+ro+' '+ro+' 0 '+large+' 1 '+o1[0]+' '+o1[1]+
         ' L'+i1[0]+' '+i1[1]+' A'+ri+' '+ri+' 0 '+large+' 0 '+i0[0]+' '+i0[1]+' Z';
}
// Top systems for a year as [{s,amt}] sorted desc, capped to top 3 (rest folded into the 3rd).
function topSystems(y){
  var m=yearSystems(y);
  var arr=SYS_ORDER.filter(function(s){return m[s];}).map(function(s){return {s:s,amt:m[s]};});
  arr.sort(function(a,b){return b.amt-a.amt;});
  if(arr.length<=3) return arr;
  var head=arr.slice(0,2), tail=arr.slice(2);
  head.push({s:tail[0].s, amt:tail.reduce(function(t,x){return t+x.amt;},0)});
  return head;
}
```

- [ ] **Step 2: Draw a donut for big multi-system future years, else keep solid**

Replace the single colored `circle` from Task 3 Step 3 with: solid fill as the base (so past/small years and the click target are unchanged), plus donut wedges overlaid when the year is big enough and genuinely mixed.

```javascript
var dom=dominantSystem(y), dc=SYS_COLOR[dom];
g.appendChild(el('circle',{cx:x,cy:laneY,r:r,fill:isPast?'none':dc,opacity:openY===y?0.95:(isPast?0.9:0.55),stroke:openY===y?'#e2e8f0':(isPast?dc:'none'),'stroke-width':isPast?1.3:1.5,'stroke-dasharray':isPast?'2 2':''}));
var tops=topSystems(y), tot=tops.reduce(function(t,x){return t+x.amt;},0);
var mixed = tops.length>=2 && (tops[0].amt/tot) < 0.75;
if(!isPast && r>=9 && mixed){
  var a=-Math.PI/2;  // start at 12 o'clock
  tops.forEach(function(p){
    var a1=a+2*Math.PI*(p.amt/tot);
    g.appendChild(el('path',{d:wedgePath(x,laneY,r*0.5,r,a,a1),fill:SYS_COLOR[p.s],opacity:openY===y?0.95:0.85,stroke:'#0f172a','stroke-width':0.5}));
    a=a1;
  });
}
```

- [ ] **Step 3: Verify visually**

Re-serve (`python -m http.server 8000`) and open `http://localhost:8000/docs/mockups/reserve-bubbles.html`. Confirm:
- 2037 (big, mixed) now shows a **donut** with violet/rose/teal wedges; the count badge still reads on top.
- Small years (e.g. a 2-item year) stay **solid** dominant — no unreadable confetti.
- Tap-to-expand, swatch dots, and legend from Task 3 still work; no console errors.

- [ ] **Step 4: Commit**

```bash
git add docs/mockups/reserve-bubbles.html
git commit -m "feat: donut markers for big multi-system reserve years"
```

---

## Self-Review (completed by plan author)

- **Spec coverage:** taxonomy+palette → Task 1/3; dominant marker → Task 3; donut → Task 4; swatch-dot list (priority) → Task 3 Step 4; legend → Task 3 Step 5; classifier-now/schema-deferred → Task 1–2 build it, schema explicitly out of scope. Quick-preview round (not touching the canonical chart) → Tasks 3–4 create a separate file. ✓
- **Placeholder scan:** every code step has complete code; no TBD/TODO. ✓
- **Type/name consistency:** `categorize`, `SYSTEMS`, and the five bucket constants are defined in Task 1 and reused verbatim in Task 2; JS `SYS`, `SYS_COLOR`, `SYS_KW`, `yearSystems`, `dominantSystem`, `topSystems`, `wedgePath` defined in Task 3 Step 2 / Task 4 Step 1 before use. ✓
