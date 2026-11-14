# cards

Two generated SVG cards for the profile README. Each comes in a light and a dark version; the README picks
one with `<picture>` and `prefers-color-scheme`.

| Script | Output | Data | Rebuilt |
|---|---|---|---|
| `stats_card.py` | `assets/stats-{light,dark}.svg` | GitHub GraphQL API, public data only | daily by `.github/workflows/stats-card.yml`, committed only when a number changes |
| `quote_card.py` | `assets/quotes-{light,dark}.svg` | the two quotes in the script | by hand, after editing a quote |

## What the stats card counts

| Row | Definition |
|---|---|
| Total stars earned | stars on the user's own public, non-fork repositories |
| Commits (last year) | commit contributions to public repositories in the last 365 days |
| Pull requests / Issues | pull requests / issues the user opened in public repositories (search `is:public`) |
| Public repositories | the user's own public, non-fork repositories |
| Languages | GitHub's per-language code size summed over the same repositories (notebook outputs count); the top three are named, the rest is "Other" |

Each count is filtered to public repositories inside the query, so a local run with a personal token (which
can also see private repositories) gives the same card as the workflow.

## Safety

- `stats_card.py` uses the standard library only, so the workflow installs nothing.
- Text from the API is HTML-escaped and language colors must be plain hex (`#RGB` / `#RRGGBB`) before they go
  into the SVG; `tests/test_profile.py` feeds hostile values to check this.
- The cards contain no scripts and load nothing external; the tests check every SVG in `assets/`.

## Quote sources

- Neale Donald Walsch; widely attributed to him, the exact book was not checked.
- Andreas Buja (2000), discussion of "Additive logistic regression: a statistical view of boosting",
  *Annals of Statistics* 28, 387–391, in the wording quoted by D. Mease and A. Wyner, "Evidence contrary to
  the statistical view of boosting", *JMLR* 9 (2008) 131–156. Buja's original text was not checked directly.

## Rebuild

```bash
python cards/stats_card.py --user Shuruyue   # token: $GITHUB_TOKEN, $GH_TOKEN or `gh auth token`
python cards/quote_card.py                   # needs Pillow and Georgia Italic for line wrapping
```

Icons are [Primer Octicons](https://github.com/primer/octicons) (MIT License, GitHub Inc.).
