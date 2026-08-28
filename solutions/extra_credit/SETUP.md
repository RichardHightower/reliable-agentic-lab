# Extra credit setup

Finish root SETUP.md first.

For assignment 2, copy the Lab 1 plugin, start the adapter, then tunnel it:

```bash
cd solutions/extra_credit/s_ext_2_ngrok
task copy-plugin
export GITHUB_WEBHOOK_SECRET=pick-a-long-random-string
task listen
# other terminal:
ngrok http 8765
```

See `solutions/extra_credit/s_ext_2_ngrok/SPEC.md` and
`labs/extra-credit/ext_2_ngrok/README.md`.

For a Droplet, see `labs/extra-credit/ext_5_digitalocean/README.md`.
