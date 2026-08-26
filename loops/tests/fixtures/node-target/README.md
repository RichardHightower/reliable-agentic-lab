# node-target

A JavaScript repo that satisfies the loop contract. It exists to prove one claim:
the loop engine is repo-agnostic.

Nothing here is Python. The engine drives it through the same `Taskfile.yml`
interface and reads the same `reports/junit.xml` and `reports/coverage.xml`.

If `loops/` ever needs a change to run against this repo, the engine is not
generic and the change is in the wrong place.
