# Spec. Extra credit 2. Expose the receiver with ngrok

No Python. You take the server from assignment 1 and give GitHub a URL for it.

Answer: the procedure below, plus
`labs/extra-credit/ext_2_ngrok/README.md` for the account details.

## Build it step by step

1. Start the receiver from assignment 1.

   ```bash
   python solutions/extra_credit/s_ext_1_webhook/webhook.py --port 8765
   ```

2. Open the tunnel.

   ```bash
   ngrok http 8765
   ```

3. Copy the HTTPS forwarding URL. Add `/github-webhook` to it.

4. Add the webhook on your fork.

   Settings, then **Webhooks**, then **Add webhook**. Content type
   `application/json`. Set a secret and put the same value in
   `GITHUB_WEBHOOK_SECRET`.

5. Subscribe to `Issues`, `Pull requests`, and `Check suites`. Nothing else.

6. Open an issue on the fork and read `work/last-webhook.json`.

## When a delivery arrives as HTML

The free ngrok interstitial is in the way. The README in the lab folder says how
to skip it.

## Verify

A delivery in the GitHub webhook log with a 200, and a matching record in
`work/last-webhook.json`.
