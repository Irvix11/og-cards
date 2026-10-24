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

## Point integration status
No verified API or event feed has been established for [OG] Point System. Until one is confirmed, staff can credit newly earned points using an audited admin command. Historical points are not imported.

This is a development build. Test it in a private Discord server before public use.
