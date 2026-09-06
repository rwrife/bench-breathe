# Companion App Plan (Local Web)

## Responsibilities
- Guide first-time device setup and connectivity checks
- Show live status and historical trend charts
- Provide session/event tagging controls
- Support local export (CSV/JSON) and local backup/restore metadata
- Surface clear device-health and data-quality states

## Setup flow
1. Discover/connect to device over local network or USB fallback.
2. Complete first-run setup and baseline capture prompts.
3. Configure sampling interval, retention horizon, and naming.
4. Start normal monitoring and event-tag workflow.

## Data ownership
- User owns all captured data
- No mandatory cloud upload in MVP
- Exports are explicit user actions only

## Protocol boundary
- App is a client of the device protocol in `docs/protocol.md`
- The app must not require hidden device endpoints or cloud-only paths
- Any schema changes require explicit versioning in protocol docs
