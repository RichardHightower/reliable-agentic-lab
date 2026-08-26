# Labs setup

Finish the root [SETUP.md](../SETUP.md) first.

```bash
git clone https://github.com/RichardHightower/reliable-agentic-lab.git
cd reliable-agentic-lab
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python scripts/verify_setup.py
```

Then:

1. Activate `.venv`.
2. Open one lab folder.
3. Paste one prompt from that lab's `prompts/` directory, or run it headless. Claude Code is not required. See [HOW-TO-RUN.md](HOW-TO-RUN.md).
4. Keep graders read-only.

```bash
source .venv/bin/activate
export PYTHONPATH="$PWD:$PWD/solutions/crm:$PWD/solutions/m2-harness"
```
