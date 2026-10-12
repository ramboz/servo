# Bounded brief → ready

Add a `--timeout` flag to `skills/agent-loop/loop.py`'s `run_goal_loop`
entrypoint. The flag takes an integer number of seconds and, when set, aborts a
single iteration that exceeds it with exit code 124, leaving the worktree
untouched. Out of scope: the heartbeat dispatch path, the `--background` runner,
and any change to the existing `--max-iterations` semantics. Stop when the new
flag has a passing unit test in `test_loop.py` and the existing suite stays
green; if the flag interacts with `--background` in a way not covered here,
stop and escalate to a human rather than guessing. Touches no secrets, deploys,
or data migrations.
