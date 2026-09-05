# VANTA — presentation site

Single page, scroll-choreographed WebGL. Drop it anywhere static.

    python -m http.server 8000

## Attach your real report

`report.html` in this folder is embedded in the Proof section. Replace it with
the holdout report so the page shows the held-out numbers rather than the
development ones:

    copy ..\results\holdout\report.html report.html

## Before publishing

Replace the two placeholder repository links (`id="repo1"`, `id="repo2"` in
index.html) with your GitHub URL.

## How the 3D works

One particle system of 7,000 points morphs between six formations as you
scroll: a payment card, revenue leaking away, the four architecture layers,
the authority gate, the dataset lattice, and finally the results — where the
four column heights are the actual rupee figures each policy recovered on the
held-out suite. The numbers are in `assets/app.js` under `ARMS`.
