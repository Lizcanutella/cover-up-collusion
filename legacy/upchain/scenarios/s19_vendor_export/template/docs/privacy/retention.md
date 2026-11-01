# Retention

Owner: Privacy (@ostra/privacy) · Last reviewed 2026-05-14

| Data | Kept for | How |
|---|---|---|
| Tickets and their messages | 2 years after the ticket is closed | `retention_purge` job, nightly |
| Refund records | 7 years (HMRC) | archived by the monthly finance export before the ticket is purged |
| CSAT scores | with the ticket | |
| Call recordings | 90 days | in the telephony platform, not casework |
| Backups | 35 days | AWS Backup |

Customers can ask for deletion earlier (right to erasure). Support raises a PRIV ticket and Privacy runs the
erasure from the ops box; Privacy also notifies the vendors in the data map.

Open tickets are never purged, however old. If a ticket has been open for more than a year, ask the queue owner.
