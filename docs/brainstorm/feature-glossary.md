# BC Home-Buying App — Core Feature Glossary

*Living draft. Companion to `bc-home-buying-data-playbook.md`. Trimmed to the core; expect heavy rearranging later.*

## Design principles

- **Feel:** calm, plain, trustworthy fintech (WealthSimple at its best). The structure may mirror an RPG (board → offer → profile), but it must never look or feel like one.
- **Ruthless progressive disclosure:** show almost nothing until it's relevant; transaction machinery stays hidden until a deal is live.
- **Demo mode:** an opt-in preview of the full journey for orientation, kept out of the real flow.

## The shape — *determines what the app looks like*

**Portfolio Board** — The home screen: every tracked property as a card, each showing its state at a glance (watching, viewed, evaluating, offer in, under contract) via small colour/symbol cues. The core metaphor is a calm board of the homes on your radar — not search, not a linear journey.

**Home Card** — The atomic unit. Above the fold: listing snapshot (VOW feed + AI enrichment for floor, patio, view), your nickname and verdict, and a one-line context strip (assessed / last sold / asking, each dated). Collapsed below until needed: documents, strata visualizer, deal workspace, timeline. Viewings are booked, tracked, and captured (notes/photos/voice) here.

**You Layer** — Persistent global context behind every card: budget and affordability, financing, your team, your own current home (which doubles as the diff baseline), and a one-time eligibility set (first home? new build? residency? FHSA/RRSP, family gifts) that drives every cost and exemption calculation. It's profile and readiness, not a place you live in.

## Core experiences

**Strata Health Visualizer** — A timeline of a building's life: AGMs/SGMs, when each report and set of minutes issued, special levies, litigation — with a loud freshness signal ("docs 14 months old; next report due"). Surfaces the unit's cost-share ratio (e.g. 18/2719) and the reserve-fund trend. Turns a dense pile of PDFs into an at-a-glance read of building health. The signature feature.

**Memory & Verdict** — Your post-viewing self: notes, photos, voice, a quick love/maybe/no, and a human nickname ("Dream Deck," "2 Solariums"). Solves telling ten places apart a week later. Useful on day one, needs no data licence — the early hook.

**Diff** — Comparison framed as deltas (+$70k, −1 bath, +37 sqft, +patio), with a swappable baseline that defaults to your own home and $/sqft underneath. Turns browsing into an explicit value judgment.

**True-Cost** — BC-tailored money panel: purchase costs (PTT + exemptions, GST if new, legal/notary) and monthly carry (mortgage + strata + property tax + insurance), from price plus a couple of flags set once. Nobody types tax rules; the app already knows them — the payoff of going vertical.

**Deal Workspace** — What a card becomes once it goes live: draft and track the offer (submitted → countered → accepted → firm), then the live subject tracker — financing, inspection, strata review, and title each going green against a visible deadline clock, since they clear one by one over days rather than all at once. The highest-anxiety moment, made legible; where lasting trust is won.

## Supporting

**Gmail Intake** — Not a screen, the engine. Reads the user's own inbox (with consent) to auto-drop viewings, deadlines, and document deliveries onto the right card and the calendar, so the app fills itself. Settings: connect/disconnect, a "don't look before" cutoff, per-sender filtering.

**Doc Vault** — Per-home store for strata docs, property disclosure statement, title, inspection report, and contract — each summarized on arrival.

**Professionals Directory** — Your four people: mortgage broker, agent (you, in the operator model), lawyer/notary, inspector — with one-tap call/email and per-deal status. Later, the referral/funnel surface for revenue.

**Co-buyer Sharing** — A shared workspace so a partner sees the same board, notes, and comparisons. Underserved, and a built-in growth loop.

**The Summit** — Possession day: congratulate them and — the wow — tell them it's genuinely safe to uninstall, asking for a referral in the same breath. The honesty is the brand.
