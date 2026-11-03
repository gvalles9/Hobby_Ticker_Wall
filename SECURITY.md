# Security Policy

## Reporting a Vulnerability

If you discover a security issue in Hobby Ticker, please report it
responsibly rather than opening a public GitHub issue. Use the private
vulnerability reporting feature for this repository when available, or
contact its maintainer privately through the hosting service.

For vulnerabilities in the original upstream FlightTracker project, use
its [security reporting instructions](https://github.com/ColinWaddell/FlightTracker/security).

Include steps to reproduce, affected versions, and potential impact.
Do not include secrets or personal data.

## Sharing Config Safely

If a security issue involves your configuration, **do not paste your raw
`config.json`** - it may contain API keys and password hashes.

Use the **"Download debug config"** button in the footer of the Settings page
in the web UI. This exports your configuration with all sensitive fields
automatically replaced with `***REDACTED***`, making it safe to share.