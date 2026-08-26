# Extra credit setup

Finish root SETUP.md first.

```bash
export PYTHONPATH="$PWD"
python solutions/extra_credit/groom_ticket.py --issue T001 --incorporate
python solutions/extra_credit/fix_pr.py --pr T001 --doer reference
python solutions/extra_credit/webhook.py --port 8765
```

Then `ngrok http 8765` or deploy the same app on a Droplet. See `labs/extra-credit/NGROK.md` and `labs/extra-credit/deploy/DIGITALOCEAN.md`.
