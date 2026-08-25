# Module 3 setup

No extra pip packages beyond the CRM file. Tests use the fixture.

```bash
pytest solutions/m3-research/tests -q
```

Optional live search:

```bash
export PERPLEXITY_API_KEY=...
```

The lab still grounds claims in `fixtures/research.json` so Saturday
does not die on signup.
