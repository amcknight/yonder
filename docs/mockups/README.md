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
