# Getting Data Into the App — BC Data Input Playbook

*Working reference for a BC (Greater Vancouver) home-buying companion app. Not legal advice — confirm specifics with a data/MLS lawyer.*

## The one rule that decides everything

**Compute & display in-context for the individual user → green.
Accumulate a standalone, cross-user, reusable dataset or product → red.**

The *operation* (diff, $/sqft, AI summary) is almost never the problem. What matters is (1) whether the output is ephemeral-for-this-user vs. accumulated-into-an-asset, and (2) **which source** the content came from — each source has its own rulebook. The channel changes *which* law bites; the line stays the same.

## The access spine

One licensed member (you or a partner) + an approved aggregator + the **VOW** tier = the key that unlocks live listings *and* anchors the rest of the business. The app **is** a VOW by design: logged-in consumers tracking a search through an app operated by a licensed member. Users are never licensed — only the operator.

## Sources at a glance

| Source | What it gives | How to access | What you may do with it | Cost / gotchas |
|---|---|---|---|---|
| **MLS listings (VOW feed)** | Active **and sold** listings, full consumer fields, photos | Be/partner w/ a Greater Vancouver REALTORS member (one connection also covers Fraser Valley + Chilliwack); connect via approved aggregator (e.g. Repliers); request **VOW**, not just IDX; pass compliance review | **Display + compute in-context** for the logged-in user. **No** data-mining, **no** redistribution, **no** derivative database/product. Retention rules apply. | Aggregator + board fees; slow compliance review; membership is the hard gate |
| **BC Assessment (Data Advice)** | Assessed values (land/improvement) + recent sales history, full provincial roll | Commercial contract via BC Assessment **Data Partnerships** team; bulk full-roll + weekly/monthly refresh (XML/CSV) | **Licensed for commercial bulk use** — store & manipulate per contract. Don't use for soliciting/harassing owners. | Quote-based pricing; not a free API. Free website lookups are non-commercial only |
| **User email (Gmail)** | Agent emails, open-house confirmations, deadlines, doc deliveries | Gmail API + OAuth user consent. Read = **restricted scope** → Google verification + **annual CASA** security assessment | Store **per-user, partitioned, for that user only**. **Never pool** into a cross-user listing DB (copyright + circumvention). | CASA recurring cost + 2–6 mo approval (<100 users to test); BC PIPA + Google limited-use/deletion rules |
| **User-supplied** (notes, photos, voice, uploaded docs) | The richest data you own | In-app capture/upload | **Yours to store & manipulate** — it's the user's own contribution, used for them | Privacy duties. Reusing one buyer's **strata docs** for another = copyright + privacy risk |
| **Public / open data** | Municipal property & tax sets, zoning, permits, land title (LTSA), census/neighbourhood | Open portals; LTSA (paid per search) | Broadly usable & manipulable per each source's terms | Mostly free/low-cost; land title is paid |
| **AI enrichment** (your derived layer) | Extracted attributes, floor-plan reads, $/sqft, diffs, summaries | You generate it | **Owned & free to manipulate IF** derived from owned/public/user inputs. Enrichment from MLS photos/remarks = **grey** (derivative) → keep ephemeral/per-user | Your real moat — but clear MLS-derived enrichment with counsel |

## What's freely manipulable vs. fenced

- **Free to own & build on:** BC Assessment (per contract), public/open data, user-supplied data, AI enrichment from those inputs. **← your defensible asset / moat**
- **Fenced (display + in-context compute only):** the MLS/VOW feed. Commodity input everyone leases identically; never your moat.

## Confirm with a data/MLS lawyer before building

1. Scope of **MLS-derived AI enrichment** (mining remarks/photos across listings is the danger zone).
2. **Cross-user reuse of strata documents** (copyright of reports/minutes + PIPA privacy).
3. **VOW** retention/display specifics in the actual board agreement.
4. **Gmail restricted-scope** use under Google's policy + CASA.

## One-line takeaways

- The buyer is a consumer; only you/your partner hold the licence.
- VOW is both the *easiest fit* and the *max-info* tier — build the app as a VOW.
- BC Assessment + user data + your enrichment = the layer you actually own.
- Email is a clean per-user input, never a back-door listing database.
