# Cron for the enhancer

One example, referenced from every sol1 port.

A poll that runs longer than the interval overlaps the next one. `flock`
refuses the overlap. The log file is the only place a failure shows up when
nobody is at the keyboard.

```bash
crontab labs/lab1_enhancer/cron/enhancer.crontab
```

Edit `DIR` to the port folder you run. `AGENT_BACKEND` is not required here
because you `cd` into that folder.

Live cron against every port: not tried. This file is the example.
