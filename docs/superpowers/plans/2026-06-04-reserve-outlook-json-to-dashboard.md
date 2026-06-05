# Reserve Outlook — JSON → Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Freeze the `ReserveOutlook` JSON contract and make the committed Reserve Trajectory mock render from it instead of hardcoded JS constants.

**Architecture:** Define `ReserveOutlook` as a Pydantic model (the seam between the future extraction half and the dashboard). A Python builder produces a synthetic, realistic sample, serialized to a committed JSON fixture via a `yonder outlook-sample` CLI command. The standalone HTML mock (`docs/mockups/reserve-trajectory.html`) fetches that JSON and derives all its constants from it; its existing in-browser model still powers the interactive fee slider. This is the first of two halves (spec: `docs/superpowers/specs/2026-06-04-reserve-trajectory-view-design.md`); the second half (`docs → json`) will *produce* this JSON from real strata docs and is **out of scope here**.

**Tech Stack:** Python 3.11+, Pydantic v2, argparse CLI, pytest (`pythonpath=src`), plain HTML/SVG/JS for the mock (no framework).

**Scope note — what this half does NOT build:** the Python `reserve_outlook()` computed-series function, classification, aggregation, or any real-document extraction. The interactive projection math lives in the mock's JS for now; the canonical Python computation arrives with the `docs → json` half, validated against this frozen contract.

**Grounding (do once before Task 1):** Skim the real depreciation report text at `fixtures/strata/Spectrum 4/Spectrum 4-Strata Docs_updated Apr 25,2025/_extracted/Depreciation report & Engineering report__DepreciationReport (2).txt` (gitignored — read locally, never commit it). Confirm the contract below covers what a real report actually carries (projected components, costs, a funding/contribution recommendation, dated ranges). If a real, load-bearing field is missing from the model, add it in Task 1; otherwise proceed. The committed sample stays synthetic ("The Wexford").

**Units convention (load-bearing):** every monetary value in the JSON is **CAD dollars** (e.g. a $420k balance is `420000`). The mock converts dollars → thousands for its chart axis on load. Monthly fees are dollars/month; `base_annual_contribution` is dollars/year.

---

### Task 1: The `ReserveOutlook` contract model

**Files:**
- Create: `src/yonder/outlook/__init__.py`
- Create: `src/yonder/outlook/model.py`
- Test: `tests/test_outlook_model.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_outlook_model.py
import json

import pytest
from pydantic import ValidationError

from yonder.outlook.model import (
    Assumptions,
    BalancePoint,
    Expenditure,
    PlannedFeeChange,
    ReserveOutlook,
    TimelineEvent,
    Unit,
)


def test_empty_outlook_is_valid_and_degraded_defaults_false():
    """Absence is first-class: an all-empty outlook must validate."""
    o = ReserveOutlook()
    assert o.expenditures == []
    assert o.history == []
    assert o.degraded is False
    assert o.start_balance is None


def test_degraded_outlook_carries_a_reason():
    o = ReserveOutlook(degraded=True, degraded_reason="no current depreciation report")
    assert o.degraded is True
    assert o.degraded_reason == "no current depreciation report"


def test_point_and_range_expenditures():
    point = Expenditure(label="Roof", amount=180000, year=2028)
    rng = Expenditure(label="Envelope", amount=1100000, start_year=2031, end_year=2033, peak_year=2032)
    assert point.year == 2028 and point.start_year is None
    assert rng.start_year == 2031 and rng.peak_year == 2032


def test_event_allows_fractional_year_and_cluster_items():
    ev = TimelineEvent(year=2027.75, row=1, type="fee", label="+10% plan")
    cluster = TimelineEvent(year=2030, row=1, type="meeting", cluster_items=["a", "b"])
    assert ev.year == 2027.75
    assert cluster.cluster_items == ["a", "b"]


def test_planned_fee_change_pct_is_fraction():
    f = PlannedFeeChange(effective_year=2028, pct=0.10)
    assert f.pct == 0.10


def test_full_outlook_round_trips_through_json():
    o = ReserveOutlook(
        unit=Unit(entitlement_numerator=18, entitlement_denominator=2719, strata_fee_monthly=486),
        assumptions=Assumptions(base_annual_contribution=90000, history_start_year=2020,
                                projection_start_year=2026, horizon_end_year=2041),
        start_balance=420000,
        history=[BalancePoint(year=2020, balance=260000)],
        expenditures=[Expenditure(label="Roof", amount=180000, year=2028)],
        planned_fee_changes=[PlannedFeeChange(effective_year=2028, pct=0.10)],
        events=[TimelineEvent(year=2028, row=0, type="work", label="Roof 180k")],
    )
    blob = o.model_dump_json()
    back = ReserveOutlook.model_validate_json(blob)
    assert back == o
    # plain-dict round trip too (what the JSON fixture exercises)
    assert ReserveOutlook.model_validate(json.loads(blob)) == o
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m uv run pytest tests/test_outlook_model.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'yonder.outlook'`

- [ ] **Step 3: Create the package init**

```python
# src/yonder/outlook/__init__.py
```

(Empty file — marks the package.)

- [ ] **Step 4: Write the model**

```python
# src/yonder/outlook/model.py
"""The ReserveOutlook contract — the JSON seam the dashboard renders from.

Carries the *inputs* the dashboard needs to both draw the chart and recompute
the fee-slider what-if client-side (start balance, history, projected
expenditures, planned fee changes, assumptions), plus presentation events.
All monetary values are CAD dollars. All fields nullable: real docs are
partial, and a missing depreciation report yields a `degraded` present-state
outlook rather than a fabricated projection.
"""

from __future__ import annotations

import datetime

from pydantic import BaseModel, Field


class BuildingMeta(BaseModel):
    name: str | None = None
    unit_label: str | None = None            # e.g. "#304"
    depreciation_report_date: datetime.date | None = None
    source_note: str | None = None           # e.g. "deprec. report 2022 · 4y old"


class Unit(BaseModel):
    entitlement_numerator: int | None = None
    entitlement_denominator: int | None = None
    strata_fee_monthly: float | None = None      # total monthly fee, dollars
    reserve_portion_monthly: float | None = None  # part of the fee going to the CRF


class BalancePoint(BaseModel):
    year: int
    balance: float                            # CRF balance, dollars


class Expenditure(BaseModel):
    """A projected major expenditure. Either a point (`year`) or a range
    (`start_year`/`end_year` with an expected `peak_year`)."""

    label: str
    amount: float                             # dollars
    year: int | None = None
    start_year: int | None = None
    end_year: int | None = None
    peak_year: int | None = None


class PlannedFeeChange(BaseModel):
    effective_year: int
    pct: float                                # fraction, e.g. 0.10 for +10%
    note: str | None = None


class TimelineEvent(BaseModel):
    """A dated marker in the bottom event lane. `year` may be fractional
    (2027.75 ≈ Oct). If `cluster_items` is set, this renders as a tap-to-expand
    count badge instead of a single labelled dot."""

    year: float
    row: int = 0                              # 0 = upper lane, 1 = lower lane
    type: str = "work"                        # "work" | "fee" | "meeting" | "levy"
    label: str | None = None
    cluster_items: list[str] | None = None


class Assumptions(BaseModel):
    interest_rate: float = 0.02               # annual, applied to the CRF balance
    base_annual_contribution: float | None = None  # dollars/year to CRF at fee_delta=0
    history_start_year: int | None = None
    projection_start_year: int | None = None  # "now"
    horizon_end_year: int | None = None
    sourced: bool = False                     # True = grounded in docs; False = placeholder


class ReserveOutlook(BaseModel):
    building: BuildingMeta = Field(default_factory=BuildingMeta)
    unit: Unit = Field(default_factory=Unit)
    assumptions: Assumptions = Field(default_factory=Assumptions)
    start_balance: float | None = None        # CRF balance at projection_start_year
    history: list[BalancePoint] = Field(default_factory=list)
    expenditures: list[Expenditure] = Field(default_factory=list)
    planned_fee_changes: list[PlannedFeeChange] = Field(default_factory=list)
    events: list[TimelineEvent] = Field(default_factory=list)
    degraded: bool = False
    degraded_reason: str | None = None
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python -m uv run pytest tests/test_outlook_model.py -q`
Expected: PASS (6 passed)

- [ ] **Step 6: Commit**

```bash
git add src/yonder/outlook/__init__.py src/yonder/outlook/model.py tests/test_outlook_model.py
git commit -m "feat: add ReserveOutlook JSON contract model"
```

---

### Task 2: Synthetic sample builder + `yonder outlook-sample` CLI + committed fixture

**Files:**
- Create: `src/yonder/outlook/sample.py`
- Modify: `src/yonder/cli.py`
- Test: `tests/test_outlook_sample.py`
- Create (generated): `fixtures/samples/reserve_outlook.sample.json`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_outlook_sample.py
import json
from pathlib import Path

from yonder.cli import main
from yonder.outlook.model import ReserveOutlook
from yonder.outlook.sample import wexford_sample


def test_wexford_sample_validates_and_has_expected_shape():
    o = wexford_sample()
    assert isinstance(o, ReserveOutlook)
    assert o.unit.entitlement_denominator == 2719
    assert o.start_balance == 420000
    # exactly one ranged expenditure (the envelope) and four point items
    ranged = [e for e in o.expenditures if e.start_year is not None]
    points = [e for e in o.expenditures if e.year is not None]
    assert len(ranged) == 1 and ranged[0].label == "Envelope"
    assert len(points) == 4
    # one cluster event present
    assert any(e.cluster_items for e in o.events)


def test_sample_round_trips_through_plain_json():
    o = wexford_sample()
    blob = o.model_dump_json()
    assert ReserveOutlook.model_validate(json.loads(blob)) == o


def test_outlook_sample_cli_writes_valid_json(tmp_path: Path):
    out = tmp_path / "sample.json"
    rc = main(["outlook-sample", str(out)])
    assert rc == 0
    loaded = ReserveOutlook.model_validate_json(out.read_text())
    assert loaded == wexford_sample()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m uv run pytest tests/test_outlook_sample.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'yonder.outlook.sample'`

- [ ] **Step 3: Write the sample builder**

```python
# src/yonder/outlook/sample.py
"""A synthetic-but-realistic ReserveOutlook ("The Wexford") — the committed
sample that drives the mock and tests. Mirrors the locked mockup's data so the
data-driven render is verifiably identical. NOT real building data."""

from __future__ import annotations

from yonder.outlook.model import (
    Assumptions,
    BalancePoint,
    BuildingMeta,
    Expenditure,
    PlannedFeeChange,
    ReserveOutlook,
    TimelineEvent,
    Unit,
)

_HISTORY = [
    (2020, 260000), (2021, 300000), (2022, 215000), (2023, 285000),
    (2024, 360000), (2025, 415000), (2026, 420000),
]


def wexford_sample() -> ReserveOutlook:
    return ReserveOutlook(
        building=BuildingMeta(
            name="The Wexford", unit_label="#304",
            source_note="deprec. report 2022 · 4y old",
        ),
        unit=Unit(
            entitlement_numerator=18, entitlement_denominator=2719,
            strata_fee_monthly=486, reserve_portion_monthly=50,
        ),
        assumptions=Assumptions(
            interest_rate=0.02, base_annual_contribution=90000,
            history_start_year=2020, projection_start_year=2026,
            horizon_end_year=2041, sourced=False,
        ),
        start_balance=420000,
        history=[BalancePoint(year=y, balance=b) for y, b in _HISTORY],
        expenditures=[
            Expenditure(label="Roof", amount=180000, year=2028),
            Expenditure(label="Plumb", amount=150000, year=2030),
            Expenditure(label="Elev", amount=240000, year=2035),
            Expenditure(label="HVAC", amount=200000, year=2038),
            Expenditure(label="Envelope", amount=1100000,
                        start_year=2031, end_year=2033, peak_year=2032),
        ],
        planned_fee_changes=[
            PlannedFeeChange(effective_year=2028, pct=0.10),
            PlannedFeeChange(effective_year=2031, pct=0.06),
        ],
        events=[
            TimelineEvent(year=2028, row=0, type="work", label="Roof 180k"),
            TimelineEvent(year=2032, row=0, type="work", label="Envelope 1.1M"),
            TimelineEvent(year=2035, row=0, type="work", label="Elev 240k"),
            TimelineEvent(year=2027.75, row=1, type="fee", label="+10% plan"),
            TimelineEvent(year=2038, row=1, type="work", label="HVAC 200k"),
            TimelineEvent(year=2030, row=1, type="meeting",
                          cluster_items=["Plumbing 150k", "+6% planned", "AGM 2030"]),
        ],
    )
```

- [ ] **Step 4: Add the CLI command**

In `src/yonder/cli.py`, add the import near the existing imports:

```python
from yonder.outlook.sample import wexford_sample
```

Add the command function (place it after `cmd_eval`):

```python
def cmd_outlook_sample(args: argparse.Namespace) -> int:
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(wexford_sample().model_dump_json(indent=2))
    print(f"wrote {out}")
    return 0
```

In `main`, register the subparser (after the `eval` subparser block, before `args = parser.parse_args(argv)`):

```python
    p_sample = sub.add_parser(
        "outlook-sample", help="Write the synthetic ReserveOutlook sample JSON."
    )
    p_sample.add_argument(
        "out", nargs="?", default="fixtures/samples/reserve_outlook.sample.json"
    )
    p_sample.set_defaults(func=cmd_outlook_sample)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python -m uv run pytest tests/test_outlook_sample.py -q`
Expected: PASS (3 passed)

- [ ] **Step 6: Generate the committed fixture**

Run: `python -m uv run yonder outlook-sample fixtures/samples/reserve_outlook.sample.json`
Expected output: `wrote fixtures/samples/reserve_outlook.sample.json`

Confirm it is valid JSON and committed (it is synthetic — safe to commit, unlike `fixtures/strata/`):

Run: `python -m uv run python -c "import json; json.load(open('fixtures/samples/reserve_outlook.sample.json')); print('ok')"`
Expected: `ok`

- [ ] **Step 7: Commit**

```bash
git add src/yonder/outlook/sample.py src/yonder/cli.py tests/test_outlook_sample.py fixtures/samples/reserve_outlook.sample.json
git commit -m "feat: add Wexford ReserveOutlook sample + outlook-sample CLI + fixture"
```

---

### Task 3: Contract-guard test (the fixture has what the mock consumes)

The mock's JS reads specific keys from the JSON. This test fails loudly if the contract drifts away from what the renderer needs — the only automated guard on the JS↔JSON seam.

**Files:**
- Test: `tests/test_outlook_fixture_contract.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_outlook_fixture_contract.py
"""Guards the JSON↔mock seam: the committed fixture must carry every field the
dashboard (docs/mockups/reserve-trajectory.html) derives its constants from."""

import json
from pathlib import Path

FIXTURE = Path("fixtures/samples/reserve_outlook.sample.json")


def _load() -> dict:
    return json.loads(FIXTURE.read_text())


def test_fixture_exists_and_parses():
    assert FIXTURE.exists(), "run: yonder outlook-sample"
    _load()


def test_assumptions_carry_projection_window_and_contribution():
    a = _load()["assumptions"]
    for key in ("base_annual_contribution", "history_start_year",
                "projection_start_year", "horizon_end_year", "interest_rate"):
        assert a[key] is not None, f"assumptions.{key} missing"


def test_unit_carries_entitlement_and_fee():
    u = _load()["unit"]
    assert u["entitlement_numerator"] and u["entitlement_denominator"]
    assert u["strata_fee_monthly"] and u["reserve_portion_monthly"]


def test_has_history_point_expenditures_and_one_range():
    o = _load()
    assert o["start_balance"] is not None
    assert len(o["history"]) >= 2
    assert any(e.get("year") is not None for e in o["expenditures"])
    assert any(e.get("start_year") is not None for e in o["expenditures"])


def test_has_events_including_a_cluster():
    events = _load()["events"]
    assert events
    assert any(e.get("cluster_items") for e in events)
```

- [ ] **Step 2: Run the test to verify it passes**

(The fixture already exists from Task 2, so this test should pass immediately — it documents and locks the contract.)

Run: `python -m uv run pytest tests/test_outlook_fixture_contract.py -q`
Expected: PASS (5 passed)

- [ ] **Step 3: Commit**

```bash
git add tests/test_outlook_fixture_contract.py
git commit -m "test: guard the ReserveOutlook JSON↔mock seam"
```

---

### Task 4: Make the mock render from the JSON

Replace the mock's hardcoded constants with values derived from the fetched JSON. The existing chart/sim/event logic is unchanged — it's wrapped in an `init(outlook)` function and fed from the fixture. A `rangeWork` guard is added so a degraded outlook (no ranged expenditure) still renders.

**Files:**
- Modify: `docs/mockups/reserve-trajectory.html` (replace the entire `<script>…</script>` block)
- Create: `docs/mockups/README.md`

- [ ] **Step 1: Replace the `<script>` block**

In `docs/mockups/reserve-trajectory.html`, replace everything from `<script>` to `</script>` (inclusive) with exactly this:

```html
<script>
(function(){
  var NS='http://www.w3.org/2000/svg', D=String.fromCharCode(36);

  function init(o){
    var a=o.assumptions||{}, u=o.unit||{};
    // ---- derive constants from the ReserveOutlook JSON (dollars -> $k for the chart) ----
    var actual={}; (o.history||[]).forEach(function(p){ actual[p.year]=p.balance/1000; });
    var pointWork={}, rangeWork=null;
    (o.expenditures||[]).forEach(function(e){
      if(e.start_year!=null){ rangeWork={start:e.start_year,end:e.end_year,peak:e.peak_year||e.start_year,amt:e.amount/1000,label:e.label}; }
      else { pointWork[e.year]={amt:e.amount/1000,label:e.label}; }
    });
    var feeSchedule={}; (o.planned_fee_changes||[]).forEach(function(f){ feeSchedule[f.effective_year]=f.pct; });
    var startBal=(o.start_balance||0)/1000, baseAnnual=(a.base_annual_contribution||0)/1000;
    var interest=a.interest_rate!=null?a.interest_rate:0.02;
    var unitShare=(u.entitlement_numerator&&u.entitlement_denominator)?(u.entitlement_numerator/u.entitlement_denominator):0;
    var baseFee=u.strata_fee_monthly||0, resBase=u.reserve_portion_monthly||0;
    var NOW=a.projection_start_year, Y0=a.history_start_year, Y1=a.horizon_end_year;
    var events=(o.events||[]).map(function(ev){
      return ev.cluster_items?{cluster:true,x:ev.year,row:ev.row||0,items:ev.cluster_items}
                             :{x:ev.year,row:ev.row||0,type:ev.type,label:ev.label};
    });
    if(o.building&&o.building.name){ document.querySelector('.bname').textContent=o.building.name+(o.building.unit_label?(' · '+o.building.unit_label):''); }
    if(o.building&&o.building.source_note){ document.querySelector('.stale').textContent=o.building.source_note; }

    var X0=46, X1=350, T=26, B=200, VMAX=1300, VMIN=-500, gridVals=[1000,500,0,-500];
    function mapX(y){return X0+(y-Y0)*(X1-X0)/(Y1-Y0);}
    function mapY(v){return T+(VMAX-v)*(B-T)/(VMAX-VMIN);}
    var zeroY=mapY(0), nowX=mapX(NOW);
    function money(v){ if(v===0) return D+'0'; var s=(Math.abs(v)>=1000)?(D+(Math.abs(v)/1000).toFixed(1)+'M'):(D+Math.abs(v)+'k'); return (v<0?'-':'')+s; }
    function el(tag,at,txt){var e=document.createElementNS(NS,tag);for(var k in at)e.setAttribute(k,at[k]);if(txt!=null)e.textContent=txt;return e;}
    function feeFactor(y){ var f=1; for(var k in feeSchedule){ if(+k<=y) f*=(1+feeSchedule[k]); } return f; }

    function sim(incr){
      var wl=startBal, ul=startBal, wlA=[{y:NOW,b:wl}], ulA=[{y:NOW,b:ul}], levies=[];
      for(var y=NOW+1;y<=Y1;y++){
        var contrib=baseAnnual*(1+incr)*feeFactor(y), e=(pointWork[y]&&pointWork[y].amt)||0;
        if(rangeWork&&y===rangeWork.peak) e+=rangeWork.amt;
        ul = ul*(1+interest)+contrib - e;
        var pre = wl*(1+interest)+contrib - e;
        if(pre<0){ var lv=-pre; levies.push({y:y,total:lv,perUnit:lv*1000*unitShare}); wl=0; }
        else wl=pre;
        wlA.push({y:y,b:wl}); ulA.push({y:y,b:ul});
      }
      return {wlA:wlA, ulA:ulA, levies:levies, totUnit:levies.reduce(function(s,L){return s+L.perUnit;},0)};
    }

    var colors={work:'#6366f1',fee:'#fbbf24',meeting:'#94a3b8',levy:'#22c55e'};
    var rowDotY=[214,232], rowLblY=[226,244];
    var clusterOpen=false, cur=0;
    var svg=document.getElementById('chart');

    function drawEvents(){
      events.forEach(function(ev){
        var ex=mapX(ev.x), dy=rowDotY[ev.row], ly=rowLblY[ev.row];
        svg.appendChild(el('line',{x1:ex,y1:B,x2:ex,y2:dy-7,stroke:'#475569','stroke-width':1,opacity:0.5}));
        if(ev.type==='fee'){ svg.appendChild(el('line',{x1:ex,y1:T,x2:ex,y2:B,stroke:'#fbbf24','stroke-dasharray':'2 3','stroke-width':1,opacity:0.4})); }
        if(ev.cluster){
          var g=el('g',{onclick:'__tc()',style:'cursor:pointer'});
          g.appendChild(el('circle',{cx:ex,cy:dy,r:8,fill:'#1e293b',stroke:'#94a3b8','stroke-width':1.2}));
          g.appendChild(el('text',{x:ex,y:dy+3.5,'text-anchor':'middle','font-size':10,fill:'#e2e8f0'},clusterOpen?'×':String(ev.items.length)));
          svg.appendChild(g);
          if(clusterOpen){ ev.items.forEach(function(it,i){
            svg.appendChild(el('text',{x:ex,y:dy+20+i*12,'text-anchor':'middle','font-size':8,fill:'#cbd5e1'},it)); }); }
        } else {
          svg.appendChild(el('circle',{cx:ex,cy:dy,r:3,fill:colors[ev.type]||'#94a3b8'}));
          svg.appendChild(el('text',{x:ex,y:ly+5,'text-anchor':'middle','font-size':8,fill:'#cbd5e1'},ev.label));
        }
      });
    }

    function draw(incr){
      cur=incr; svg.innerHTML='';
      [Y0,Y0+3,NOW,NOW+3,NOW+6,NOW+9,NOW+12,Y1].forEach(function(yr){
        if(yr<Y0||yr>Y1) return;
        var z=(yr===NOW);
        svg.appendChild(el('text',{x:mapX(yr),y:12,'text-anchor':'middle','font-size':9,fill:z?'#22c55e':'#475569'},z?'now':String(yr))); });
      gridVals.forEach(function(v){ var gy=mapY(v),z=(v===0);
        svg.appendChild(el('line',{x1:X0,y1:gy,x2:X1,y2:gy,stroke:z?'#64748b':'#334155','stroke-width':1,'stroke-dasharray':z?'3 3':'2 4'}));
        svg.appendChild(el('text',{x:X0-6,y:gy+3,'text-anchor':'end','font-size':10,fill:z?'#94a3b8':'#64748b'},money(v))); });
      svg.appendChild(el('rect',{x:X0,y:T,width:nowX-X0,height:B-T,fill:'#ffffff',opacity:0.03}));
      svg.appendChild(el('line',{x1:nowX,y1:T,x2:nowX,y2:B,stroke:'#22c55e','stroke-width':1.5,opacity:0.8}));

      var s=sim(incr);
      s.levies.forEach(function(L){ var h=L.total*(B-T)/(VMAX-VMIN);
        svg.appendChild(el('rect',{x:mapX(L.y)-6,y:Math.max(zeroY-h,T),width:12,height:Math.min(h,zeroY-T),rx:2,fill:'#22c55e',opacity:0.5}));
        svg.appendChild(el('text',{x:mapX(L.y),y:Math.max(zeroY-h,T)-3,'text-anchor':'middle','font-size':8.5,fill:'#86efac'},'+'+D+Math.round(L.perUnit).toLocaleString()+'/u'));
      });
      if(rangeWork){ var rh=rangeWork.amt*(B-T)/(VMAX-VMIN);
        svg.appendChild(el('rect',{x:mapX(rangeWork.start),y:zeroY,width:mapX(rangeWork.end)-mapX(rangeWork.start),height:Math.min(rh,B-zeroY),rx:2,fill:'#6366f1',opacity:0.28}));
        svg.appendChild(el('rect',{x:mapX(rangeWork.peak)-2,y:zeroY,width:4,height:Math.min(rh,B-zeroY),fill:'#6366f1',opacity:0.6})); }
      for(var y in pointWork){ var amt=pointWork[y].amt, h2=amt*(B-T)/(VMAX-VMIN);
        svg.appendChild(el('rect',{x:mapX(+y)-5,y:zeroY,width:10,height:Math.min(h2,B-zeroY),rx:2,fill:'#6366f1',opacity:0.6})); }

      var aPts=[]; for(var ya=Y0;ya<=NOW;ya++){ if(actual[ya]!=null) aPts.push(mapX(ya)+','+mapY(actual[ya])); }
      svg.appendChild(el('polyline',{points:aPts.join(' '),fill:'none',stroke:'#38bdf8','stroke-width':2.5,'stroke-linejoin':'round'}));
      var ulPts=s.ulA.map(function(p){return mapX(p.y)+','+mapY(Math.max(p.b,VMIN));});
      svg.appendChild(el('polyline',{points:ulPts.join(' '),fill:'none',stroke:'#f59e0b','stroke-width':1.6,'stroke-dasharray':'4 3',opacity:0.7}));
      var wlPts=s.wlA.map(function(p){return mapX(p.y)+','+mapY(p.b);});
      svg.appendChild(el('polyline',{points:wlPts.join(' '),fill:'none',stroke:'#22c55e','stroke-width':2.6,'stroke-linejoin':'round'}));

      drawEvents();

      document.getElementById('pctLabel').textContent=(incr>=0?'+':'')+Math.round(incr*100)+'%';
      var newFee=Math.round(baseFee+resBase*incr), newRes=Math.round(resBase*(1+incr));
      var feeEl=document.getElementById('feeOut'); feeEl.textContent=D+newFee; feeEl.style.color=incr!==0?'#fbbf24':'#e2e8f0';
      document.getElementById('resOut').textContent=D+newRes;
      var levyEl=document.getElementById('levyOut'), verdict=document.getElementById('verdict');
      if(s.levies.length===0){
        levyEl.textContent=D+'0'; levyEl.style.color='#22c55e';
        verdict.innerHTML='<span style="color:#22c55e">&#10003; No levies needed</span> &mdash; planned increases + your slider cover every project.';
      } else {
        levyEl.textContent='~'+D+Math.round(s.totUnit).toLocaleString(); levyEl.style.color='#ef4444';
        var first=s.levies[0];
        verdict.innerHTML='<span style="color:#f59e0b">'+s.levies.length+' levy'+(s.levies.length>1?'s':'')+'</span> &mdash; first '+first.y+' (~'+D+Math.round(first.perUnit).toLocaleString()+'/unit). Fund tops back to $0.';
      }
    }
    window.__tc=function(){ clusterOpen=!clusterOpen; draw(cur); };
    var slider=document.getElementById('slider');
    slider.addEventListener('input',function(){ draw(slider.value/100); });
    draw(0);
  }

  function fail(msg){ var v=document.getElementById('verdict'); if(v) v.textContent=msg; }
  fetch('../../fixtures/samples/reserve_outlook.sample.json')
    .then(function(r){ if(!r.ok) throw new Error('HTTP '+r.status); return r.json(); })
    .then(init)
    .catch(function(e){ fail('Could not load reserve_outlook.sample.json. Serve the repo root over http (python -m http.server) and open this page via http://localhost:8000/docs/mockups/reserve-trajectory.html  ['+e.message+']'); });
})();
</script>
```

- [ ] **Step 2: Write the run instructions**

```markdown
<!-- docs/mockups/README.md -->
# Reserve Trajectory mockup

`reserve-trajectory.html` renders the locked Reserve Trajectory view from
`fixtures/samples/reserve_outlook.sample.json` (the frozen `ReserveOutlook`
contract). It fetches the JSON, so it must be served over HTTP — opening the
file directly (`file://`) will show a load error.

## Run

From the repo root:

```bash
python -m http.server 8000
```

Then open: http://localhost:8000/docs/mockups/reserve-trajectory.html

Drag the fee slider to explore the what-if. To change the data, edit the
builder and regenerate the fixture:

```bash
python -m uv run yonder outlook-sample fixtures/samples/reserve_outlook.sample.json
```
```

- [ ] **Step 3: Verify in the browser (manual)**

Run (leave it running): `python -m http.server 8000`
Open: `http://localhost:8000/docs/mockups/reserve-trajectory.html`

Confirm:
- The chart renders (cyan actual line → green projected line, indigo work bars, envelope range band, two-row event lane, ③ cluster).
- Header reads **The Wexford · #304**.
- At **+0%** the verdict is amber ("levy … first 2032 …"); dragging the slider toward **+100%** flips it green ("No levies needed").
- Tapping the **③** dot fans out the cluster.

This should look identical to the pre-refactor mock — it's now driven by the JSON instead of inline constants.

- [ ] **Step 4: Commit**

```bash
git add docs/mockups/reserve-trajectory.html docs/mockups/README.md
git commit -m "feat: drive Reserve Trajectory mock from the ReserveOutlook JSON"
```

---

## Self-Review

**Spec coverage** (against `2026-06-04-reserve-trajectory-view-design.md`):
- "Freeze the `ReserveOutlook` JSON shape" → Task 1 (model) + Task 3 (contract guard). ✓
- "Hand-author a realistic instance … rewire the committed mock to consume that JSON" → Task 2 (sample/fixture) + Task 4 (mock). ✓
- "Storage = JSON for the prototype" → JSON fixture is the only store. ✓
- "Selective extraction / depreciation report keystone / Python `reserve_outlook` / classify / aggregate" → **correctly deferred** to the `docs → json` half per the build-order section; explicitly out of scope here. ✓
- "Graceful degradation (degraded flag)" → modeled in Task 1 (`degraded`/`degraded_reason`) and the mock's `rangeWork` guard tolerates a projection-less outlook; full degraded *rendering* is exercised in the second half. ✓
- "Deferred UI-polish notes (label collision, readout color, cluster popover)" → not in scope; untouched. ✓

**Placeholder scan:** no TBD/TODO; every code step shows complete code; the only manual step (Task 4 Step 3) is a browser check with explicit pass criteria. ✓

**Type consistency:** model field names (`base_annual_contribution`, `projection_start_year`, `strata_fee_monthly`, `reserve_portion_monthly`, `entitlement_numerator/denominator`, `start_balance`, `cluster_items`, `peak_year`) are used identically in `sample.py`, the contract-guard test, and the mock's `init()` derivation. The CLI subcommand name `outlook-sample` matches between `main()` registration and the test invocation. ✓

**Note on the two model implementations:** the projection math exists in Python's future `reserve_outlook()` (next half) *and* in the mock's JS `sim()` (here). This duplication is deliberate and temporary — the JS powers the standalone interactive what-if; the Python version becomes canonical when the backend renders. The frozen JSON contract is what keeps them aligned.
