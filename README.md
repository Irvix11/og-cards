# OG Cards — Discord Bot

A collectible trading-card bot for OG Clan.

## Features
- One pack per **10,000 newly credited OG points**; progress starts at zero for all members.
- Random card packs with rarity odds: Common 50%, Rare 27%, Epic 15%, Legendary 7%, Mythic 1%.
- Epic, Legendary, and Mythic pulls can be announced in a configured channel.
- Card-for-card trading: offer, incoming offers, accept, cancel/decline, and trade history.
- Pending trade cards are locked to prevent simultaneous offers; trades expire after 24 hours.
- Admin commands are restricted to the configured **ADMIN_ROLE_ID** role. Discord Administrator permission alone does not bypass this check.
- Staff can manually credit newly earned points until a verified integration with [OG] Point System is available.
- SQLite for local development; keep the database file on persistent storage when hosted.

## Commands
- `/cards profile`, `/cards progress`, `/cards collection`, `/cards catalogue`, `/cards open`
- `/trade offer`, `/trade incoming`, `/trade accept`, `/trade cancel`, `/trade history`
- `/admin add-points`, `/admin audit-recent`

## Run locally
1. Install Python 3.11 or newer.
2. Create a virtual environment and run `pip install -r requirements.txt`.
3. Copy `.env.example` to `.env`.
4. Set `DISCORD_TOKEN` and the Discord role ID for `ADMIN_ROLE_ID`. Optionally set `TEST_GUILD_ID` and `RARE_PULL_CHANNEL_ID`.
5. Run `python bot.py`.

Invite the bot with the `bot` and `applications.commands` scopes. Never commit `.env`, bot tokens, or database files.

## Hosting direction
Use a dedicated persistent Oracle Cloud VM process, separate from Football Auction League, with persistent database storage and backups.

## Before launch
- [ ] Create the Discord application and bot; keep the token private.
- [ ] Invite it with the `bot` and `applications.commands` scopes.
- [ ] Set `ADMIN_ROLE_ID` to the exact OG Cards staff role ID. Leave it blank until ready; no one can use admin commands while it is blank.
- [ ] Optionally configure `TEST_GUILD_ID` for fast command registration while testing.
- [ ] Optionally configure `RARE_PULL_CHANNEL_ID` for Epic, Legendary, and Mythic announcements.
- [ ] Test packs, trades, permissions, restart recovery, and backups in a private server.
- [ ] Use a persistent disk for `DATABASE_PATH`; do not store the SQLite database on an ephemeral filesystem.
- [ ] Back up the database regularly and test restoring a backup before launch.
- [ ] Keep logs and the database private; never publish `.env` or the SQLite file.

## Oracle Cloud VM notes
Use a dedicated Linux VM process for the bot, separate from Football Auction League. Install Python 3.11+, clone this repository, create a virtual environment, install requirements, configure `.env`, and run the bot under a process manager such as systemd so it restarts after a crash or reboot. Keep the database on the VM's persistent boot/block volume and back it up to a separate location. Do not expose SQLite or the bot token publicly.

A simple SQLite backup while the bot is running can be made with Python's SQLite backup API:
```bash
mkdir -p backups
python - <<'PY'
import sqlite3
source = sqlite3.connect('data/og_cards.sqlite3')
target = sqlite3.connect('backups/og_cards-backup.sqlite3')
source.backup(target)
target.close()
source.close()
PY
```
Adjust paths to match `DATABASE_PATH`. Keep multiple dated backups rather than overwriting the only copy.

## Point integration status
No verified API or event feed has been established for [OG] Point System. Until one is confirmed, staff can credit newly earned points using `/admin add-points`; every credit is recorded in the audit ledger. Use a clear reason/source reference for each credit and verify the source bot's totals before entering points. Historical points are not imported and all members start at zero.

This is still a development build until the private-server checklist has been completed and the bot has been deployed. Artwork is intentionally deferred.
