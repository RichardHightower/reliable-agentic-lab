# Lab setup

Everything is in the root [SETUP.md](../SETUP.md). Run it once.

```bash
task setup
```

That creates the virtualenv, installs dependencies, clones the target repo into
`work/`, and verifies the result.

## Then work from a lab folder

```bash
cd labs/lab1_enhancer
task test
```

`task` works from any lab folder. Each lab's `Taskfile.yml` reaches the root one.

## No PYTHONPATH

Each lab folder carries a copy of `_root.py`. Your stub imports it and the repo
root lands on `sys.path`. Nothing to export, nothing to remember.
