# Ticket architecture

A ticket is a file. Git is the system of record.

Frontmatter:

```yaml
id: T001
title: Customers need to know when tasks are due
state: ready
loop: implementer
```

`## Success criteria` is a list of machine-checkable bullets.
That list is what `solutions/m2-harness` loads as the rubric.
