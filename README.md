# OG Cards — Discord Bot

A collectible trading-card bot for OG Clan, separate from Football Auction League.

## Planned features
- Slash commands for profile, collection, catalogue, pack opening, and progress.
- One pack per 50,000 newly credited OG points.
- Rarity odds: Common 50%, Rare 27%, Epic 15%, Legendary 7%, Mythic 1%.
- Duplicate cards allowed; trading is a planned milestone.
- SQLite for local development; persistent storage required when hosted.
- Admin-only manual point crediting until a verified integration with the existing `[OG] Point System` is available.

## Run locally
1. Install Python 3.11 or newer.
2. Create a virtual environment and run `pip install -r requirements.txt`.
3. Copy `.env.example` to `.env` and set `DISCORD_TOKEN`.
4. Run `python bot.py`.

Invite the bot with the `bot` and `applications.commands` scopes. Never commit `.env`, bot tokens, or database files.

## Hosting direction
Use a dedicated persistent Oracle Cloud VM process, following the general hosting approach used by Football Auction League. Run this as its own service and keep its database on persistent storage. Before public launch, add PostgreSQL support, backups, monitoring, and trade-system tests.

## Point integration status
No verified API or event feed has been established for `[OG] Point System`. Until one is confirmed, staff can credit newly earned points using an audited admin command. Profiles start at zero at launch; historical lifetime points are not imported.

This is the initial foundation, not a finished public launch. Test in a private server before inviting the bot to the main OG server.
