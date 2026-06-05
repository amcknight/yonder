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

## Rendering real extracted data

`yonder outlook <report.pdf>` writes a `*.reserve_outlook.json` next to the PDF
(under the gitignored `fixtures/strata/`). Point the mock at it with the `?data=`
query param (path is relative to this HTML file), e.g.:

```
http://localhost:8000/docs/mockups/reserve-trajectory.html?data=../../fixtures/strata/<building>/<report>.reserve_outlook.json
```

With no `?data=`, the committed synthetic Wexford sample is shown. Real building
data stays gitignored; the http server still serves it locally.
