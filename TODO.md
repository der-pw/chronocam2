# TODO

## Performance & Load
- Optionally refresh cached stats in a periodic background task (e.g., every 60s) instead of scanning on each request.
- Consider pausing/throttling the client clock update when the tab is hidden to reduce background wakeups.

## UX / Status Messaging
- Keep unified status line but clarify source (healthcheck vs snapshot) if needed.
- Consider showing reconnect/status warnings only after multiple consecutive failures and tune threshold as needed.

## Browser Load
- 1s clock updates in inactive tabs can be throttled via `visibilitychange`.

## Server Load
 

## Healthcheck
- Expose healthcheck status on UI more explicitly if users want to distinguish reachability vs snapshot failures.
