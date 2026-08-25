# Module 2 troubleshooting

## ImportError: harness.loops

Imports are `loops.implementer`. Set `PYTHONPATH=solutions/m2-harness`.

## Maker writes a README and blows up

Writes are scoped. Skip anything not in the due-date file list.

## Gate retries forever

It will not. Budget and repeat detection escalate. If you think it looped,
open `traces/last-loop.json` and read `gate`.
