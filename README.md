# OG Cards — Discord Bot

A collectible trading-card bot for OG Clan, separate from Football Auction League.

## Current features
- Slash commands for profiles, progress, collections, catalogue, pack opening, and replay submissions.
- One pack per **10,000 newly credited OG points**. Progress starts at zero for everyone at launch; historical points are not imported.
- Rarity odds: Common 50%, Rare 27%, Epic 15%, Legendary 7%, Mythic 1%.
- Epic, Legendary, and Mythic pulls can be announced in a configured Discord channel.
- Members can submit one or two replay links for staff review. Staff can approve a submission and award a random catalogue card, or reject it.
- Duplicate cards are allowed. Secure player-to-player trading and gold trading are planned next.
- SQLite for local development; keep the database file on persistent storage when hosted.
- Admin-only manual point crediting until a verified integration with `[OG] Point System` is available.

## Commands
- `/cards profile`, `/cards progress`, `/cards collection`, `/cards catalogue`, `/cards open`
- `/replay submit`
- `/admin add-points`, `/admin audit-recent`, `/admin replay-pending`, `/admin replay-review`

## Run locally
1. Install Python 3.11 or newer.
2. Create a virtual environment and run `pip install -r requirements.txt`.
3. Copy `.env.example` to `.env` and set `DISCORD_TOKEN`.
4. Configure `ADMIN_ROLE_IDS` with trusted staff role IDs. Optionally set `TEST_GUILD_ID` for fast command syncing and `RARE_PULL_CHANNEL_ID` for pull announcements.
5. Run `python bot.py`.

Invite the bot with the `bot` and `applications.commands` scopes. Never commit `.env`, bot tokens, or database files.

## Hosting direction
Use a dedicated persistent Oracle Cloud VM process, following the general hosting approach used by Football Auction League. Run this as its own service and keep its database on persistent storage. Before public launch, add backups, monitoring, and trade-system tests.

## Point integration status
No verified API or event feed has been established for `[OG] Point System`. Until one is confirmed, staff can credit newly earned points using an audited admin command. Do not scrape private bot data or assume access to its database.

This is still a development build. Test in a private Discord server before public use.
