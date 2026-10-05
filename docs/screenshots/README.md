# Actual application screenshots

The nine PNGs are captures of the running Flask interface with fictional seeded
records. They are standardized to 1440 × 900, with no browser chrome or developer
tools. The capture service scales some images slightly; those captures are
resampled to the same dimensions without changing their content.

## Refreshing the captures

Use a separate local database to keep existing account data out of public images.
In PowerShell, after installing the project dependencies:

```powershell
$env:DATABASE_URL = 'sqlite:///portfolio-demo.db'
python seed.py
python -m flask --app run.py run --host 127.0.0.1 --port 5057
```

Open http://127.0.0.1:5057 with a desktop viewport of 1440 × 900. Use accounts from
the main README's Demo Credentials section. Dismiss login alerts and verify charts
have rendered before capturing. Keep the default light appearance.

| File | View |
| --- | --- |
| `landing-page.png` | Public homepage before login |
| `dashboard.png` | alexjohnson dashboard, cards, charts, recent activity |
| `organizer.png` | Organizer with fictional Demo Downloads entered, without submitting |
| `preview.png` | Organizer's **View demo preview** link; fictional read-only plan |
| `rules.png` | Populated personal and default rules |
| `statistics.png` | File totals and rendered analytics charts |
| `history.png` | Four illustrative sessions with varied dates |
| `admin-dashboard.png` | Global cards, charts, and recent operations |
| `admin-users.png` | Six active demo accounts and their roles |

Also inspect Scheduled tasks and Admin activity logs for populated rows. All demo
paths must start with `C:/Users/Demo` or `/home/demo`. Do not capture Settings,
which can show the actual machine's approved roots. Never use personal files or
create blank images. Save real PNG files and check the main README's image links.
Demo previews cannot execute; demo schedules are always skipped by the worker.
