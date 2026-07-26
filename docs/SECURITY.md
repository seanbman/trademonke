# Security

Dry-run and spot mode are validated at application startup. Freqtrade starts stopped, force entry is disabled, and its REST service is loopback-only. The MVP must not receive exchange keys. PostgreSQL is not published to the host.

Use generated passwords, restrictive host permissions, firewall/SSH controls, encrypted off-host backups, dependency/image updates, and secret rotation. Do not log tokens, credentials, full private configuration, or Telegram secrets. A future reviewed task is required before any live-trading path exists.

