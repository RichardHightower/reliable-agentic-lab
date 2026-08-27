# Extra credit setup

Finish root SETUP.md first.

```bash
export PYTHONPATH="$PWD"
python solutions/extra_credit/s_ext_3_groom_ticket/groom_ticket.py --issue T001 --incorporate
python solutions/extra_credit/s_ext_4_fix_pr/fix_pr.py --pr T001 --doer reference
python solutions/extra_credit/s_ext_1_webhook/webhook.py --port 8765
```

Then `ngrok http 8765` or deploy the same app on a Droplet. See `labs/extra-credit/ext_2_ngrok/README.md` and `labs/extra-credit/ext_5_digitalocean/README.md`.
