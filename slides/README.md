# Slides

Marp markdown. Four sessions. Same titles as Eventbrite.

Saturday 29 August 2026. Teach 10:00 to 15:00 Central.
Open plus four modules plus close. Three breaks. 240 minutes.

```
slides/
  README.md
  FEATURE-MAP.md              which loop feature each session introduces
  mermaid.json                Spillwave theme for mermaid-cli
  themes/spillwave.css        reusable Marp theme
  diagrams/mermaid/           editable .mmd source
  diagrams/plantuml/          editable .puml source plus SVG
  diagrams/imagen/            Spillwave theme contract for raster enhancement
  session-1-system-architecture/
  session-2-harness-engineering/
  session-3-research-loops-mcp/
  session-4-production-architecture/
```

Each session folder:

| File | Role |
|---|---|
| `slides.md` | Deck. One Marp slide per `---` block. Source of truth. |
| `slides.build.md` | Generated. Mermaid blocks replaced with SVG. |
| `notes.md` | Narrative for that session. Same images, spoken order. |
| `images/` | Editorial JPGs plus mermaid-cli SVGs. |

Mermaid is not drawn by Marp. Render first:

```bash
python scripts/build_slides.py
npx @marp-team/marp-cli slides/session-1-system-architecture/slides.build.md --pdf \
  --allow-local-files --html
```

If Chromium is not where mermaid-cli expects it, set
`PUPPETEER_EXECUTABLE_PATH` or `MERMAID_PUPPETEER_CONFIG`. The build script
also looks for Playwright's `chrome-headless-shell` under `/opt/pw-browsers`.

Optional Marp theme, if you do not want the inline CSS in `slides.md`:

```bash
npx @marp-team/marp-cli --theme-set slides/themes slides/session-1-system-architecture/slides.build.md --pdf
```

Images can stay as prompts until Friday. Editorial stills live next to the
deck; architecture diagrams prefer mermaid-cli SVG over raster drafts.

## Layouts. Mix them.

Set `layout` in the HTML comment on every slide.

| `layout` | What the room sees |
|---|---|
| `title` | Big title. One line under it. No figure. |
| `split-right` | Bullets left. Image or mermaid right. `![bg right:42%](images/...)` |
| `split-left` | Image left. Bullets right. `![bg left:42%](images/...)` |
| `figure-bottom` | Short line at the top. Diagram takes the rest. |
| `figure-top` | Diagram first. One or two lines under it. |
| `lab` | Black terminal energy. Command. Expected output. |
| `section` | Chapter card. Module title only. |

Do not make every slide split-right. Alternate.

## Slide comment block

```markdown
<!--
id: s1-04
layout: split-right
minutes: 1
beat: talk
image: images/prompting-volume.jpg
image_prompt: >
  16:9 editorial. One engineer, many identical chat windows.
  Cool gray. One green signal. No logos. No readable UI text.
notes: Ask the room who has a prompt that worked once and never again.
-->
```

- `beat`: `talk` | `lab` | `bridge`
- `image_prompt`: fill later. Do not block the deck on art.
- Mermaid on the slide is the figure when there is no PNG yet.

## Clock

| Block | Minutes | Deck |
|---|---|---|
| Open | 10 | session 1, slides 01 to 08 |
| Module 1 talk | 15 | session 1, anatomy |
| Module 1 lab | 25 | session 1, lab |
| Module 1 bridge | 5 | session 1, break setup |
| Module 2 | 55 | session 2. Center. Do not cut. |
| Module 3 | 40 | session 3 |
| Module 4 | 35 | session 4 |
| Close | 10 | session 4, last slides |

If a lab runs long, cut talk. Do not cut Module 2.
Do not reteach 20 August. Point back, then build.

## Progressive build

The CRM stays the same object. Each session adds a loop-engineering feature.
See `FEATURE-MAP.md`.
