# Running VANTA

## Without Docker

    python3 -m venv .venv && source .venv/bin/activate
    pip install -e ".[dev]"

    pytest -q                                    # 54 tests
    vanta evaluate --suite development --no-llm --skip-llm-arm

Open `results/development/report.html`.

`--skip-llm-arm` runs arms A, B and B+ only. Drop it once the diagnosis cache
exists; without the cache, arm C raises `CacheMiss` by design rather than
silently degrading to rules-based diagnosis.

## With Docker

    docker compose up --build

Results land in `./results` on the host.

## Building the diagnosis cache (arm C)

144 buckets, one model call each, once. Then it replays for free forever.

    export ANTHROPIC_API_KEY=sk-...
    vanta build-cache
    git add data/diagnosis_cache.json

Or any OpenAI-compatible free tier:

    export VANTA_LLM_BASE_URL=https://models.inference.ai.azure.com
    export VANTA_LLM_MODEL=gpt-4o-mini
    export VANTA_LLM_API_KEY=...
    vanta build-cache

Then the full four-arm run:

    vanta evaluate --suite development --no-llm

## The holdout run

    vanta evaluate --suite holdout --no-llm

Refuses to run until a `POLICIES_FROZEN` file exists in the repo root (ADR-003).
Create it only when the policies are final. One run. No re-tuning.

## Useful flags

    --events N        events per seed (default 1000)
    --audit PATH      SQLite audit log location
    --report PATH     HTML report location

## Windows notes

PowerShell 5.1 has no `&&`; run the lines separately or chain with `;`.

    python -m venv .venv
    .\.venv\Scripts\Activate.ps1
    pip install -e ".[dev]"
    pytest -q
    vanta evaluate --suite development --no-llm --skip-llm-arm
    start results\development\report.html

If activation is blocked: `Set-ExecutionPolicy -Scope Process -Bypass`.

All file I/O specifies UTF-8 explicitly. Python's default text encoding on
Windows is cp1252, which cannot encode the rupee sign; relying on the platform
default would make the report generator fail there and nowhere else. CI runs on
Windows as well as Linux for exactly this reason.
