from __future__ import annotations

import os
import random
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

from database import CardStore, POINTS_PER_PACK, RARITY_ODDS, STARTER_CARDS

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN", "").strip()
ADMIN_ROLE_ID = int(os.getenv("ADMIN_ROLE_ID", "0").strip() or "0")
DB_PATH = os.getenv("DATABASE_PATH", "data/og_cards.sqlite3")
TEST_GUILD_ID = os.getenv("TEST_GUILD_ID", "").strip()
RARE_PULL_CHANNEL_ID = os.getenv("RARE_PULL_CHANNEL_ID", "").strip()

bot = commands.Bot(command_prefix="!", intents=discord.Intents.default())
store = CardStore(DB_PATH)


def is_card_admin(interaction: discord.Interaction) -> bool:
    if interaction.guild is None or not isinstance(interaction.user, discord.Member):
        return False
    return ADMIN_ROLE_ID != 0 and any(r.id == ADMIN_ROLE_ID for r in interaction.user.roles)


def admin_check():
    async def predicate(interaction: discord.Interaction) -> bool:
        if not is_card_admin(interaction):
            raise app_commands.CheckFailure("You need the configured OG Cards admin role to use this command.")
        return True
    return app_commands.check(predicate)


def roll_rarity() -> str:
    value = random.random() * 100
    cumulative = 0
    for rarity, chance in RARITY_ODDS.items():
        cumulative += chance
        if value < cumulative:
            return rarity
    return "Common"


def card_text(card: dict) -> str:
    return (f"**{card['name']}** · {card['rarity']}\nTheme: {card['theme']} · Edition: {card['edition']}\n"
            f"OVR **{card['ovr']}** | PAC {card['pac']} | ATK {card['atk']} | DEF {card['deff']} | SKL {card['skl']}")


@bot.event
async def on_ready():
    if TEST_GUILD_ID.isdigit():
        guild = discord.Object(id=int(TEST_GUILD_ID))
        bot.tree.copy_global_to(guild=guild)
        await bot.tree.sync(guild=guild)
        print(f"Logged in as {bot.user}; synced commands to test guild {TEST_GUILD_ID}")
    else:
        await bot.tree.sync()
        print(f"Logged in as {bot.user}; synced global commands")


cards = app_commands.Group(name="cards", description="Your OG Clan collectible cards")
bot.tree.add_command(cards)


@cards.command(name="profile", description="View your points and pack progress")
async def profile(interaction: discord.Interaction):
    p = store.get_profile(interaction.guild_id, interaction.user.id)
    await interaction.response.send_message(
        f"**{interaction.user.display_name} — OG Cards**\nPoints since launch: **{p['points_total']:,}**\n"
        f"Unopened packs: **{p['packs']}**\nCards collected: **{p['card_count']}**\n"
        f"Progress: **{p['progress']:,}/{POINTS_PER_PACK:,}** points", ephemeral=True)


@cards.command(name="progress", description="Check your progress toward the next pack")
async def progress(interaction: discord.Interaction):
    p = store.get_profile(interaction.guild_id, interaction.user.id)
    await interaction.response.send_message(
        f"Progress: **{p['progress']:,}/{POINTS_PER_PACK:,}** points; **{POINTS_PER_PACK-p['progress']:,}** points to next pack.",
        ephemeral=True)


@cards.command(name="collection", description="View your collection or another member's collection")
@app_commands.describe(member="Optional member whose collection you want to view")
async def collection(interaction: discord.Interaction, member: discord.Member | None = None):
    target = member or interaction.user
    items = store.get_collection(interaction.guild_id, target.id)
    if not items:
        await interaction.response.send_message(f"{target.display_name} has no cards yet. Earn points and open a pack!", ephemeral=True)
        return
    lines = [f"**#{c['instance_id']} {c['name']}** · {c['rarity']} · OVR {c['ovr']}" for c in items]
    await interaction.response.send_message(f"**{target.display_name}'s OG Cards**\n" + "\n".join(lines), ephemeral=(member is None))


@cards.command(name="catalogue", description="Browse the starter card catalogue")
async def catalogue(interaction: discord.Interaction):
    lines = [f"**{c['name']}** — {c['rarity']} · OVR {c['ovr']} · {c['theme']}" for c in STARTER_CARDS]
    await interaction.response.send_message("**OG Cards Catalogue**\n" + "\n".join(lines), ephemeral=True)


@cards.command(name="open", description="Open one earned card pack")
async def open_pack(interaction: discord.Interaction):
    if interaction.guild_id is None:
        await interaction.response.send_message("Use this command in the OG Clan server.", ephemeral=True)
        return
    rarity = roll_rarity()
    pool = [c for c in STARTER_CARDS if c["rarity"] == rarity]
    card = store.open_pack_with_card(interaction.guild_id, interaction.user.id, random.choice(pool))
    if card is None:
        await interaction.response.send_message("You don't have an unopened pack. Use /cards profile to check progress.", ephemeral=True)
        return
    colour = discord.Color.dark_red() if rarity in {"Epic", "Legendary", "Mythic"} else discord.Color.gold()
    embed = discord.Embed(title="OG CARD PACK OPENED", description=card_text(card), color=colour)
    embed.set_footer(text=f"{rarity} pull · Card instance #{card['instance_id']}")
    await interaction.response.send_message(embed=embed)
    if rarity in {"Epic", "Legendary", "Mythic"} and RARE_PULL_CHANNEL_ID.isdigit():
        channel = bot.get_channel(int(RARE_PULL_CHANNEL_ID))
        if channel is not None:
            announcement = discord.Embed(
                title=f"🔥 {rarity.upper()} OG CARD PULL!",
                description=f"{interaction.user.mention} pulled **{card['name']}**!\nOVR **{card['ovr']}** · Card #{card['instance_id']}",
                color=colour,
            )
            await channel.send(embed=announcement)



admin = app_commands.Group(name="admin", description="Staff-only OG Cards controls")
bot.tree.add_command(admin)



trades = app_commands.Group(name="trade", description="Trade OG cards with other members")
bot.tree.add_command(trades)

@trades.command(name="offer", description="Offer one of your cards for one card owned by another member")
@app_commands.describe(member="Member to trade with", your_card_id="Instance ID of your card", their_card_id="Instance ID of their card")
async def trade_offer(interaction: discord.Interaction, member: discord.Member, your_card_id: app_commands.Range[int, 1, 100000000], their_card_id: app_commands.Range[int, 1, 100000000]):
    if interaction.guild_id is None:
        await interaction.response.send_message("Use trading in the OG Clan server.", ephemeral=True)
        return
    try:
        result = store.create_trade(interaction.guild_id, interaction.user.id, member.id, your_card_id, their_card_id)
    except ValueError as exc:
        await interaction.response.send_message(str(exc), ephemeral=True)
        return
    a, b = result["proposer_card"], result["recipient_card"]
    embed = discord.Embed(title=f"OG Card Trade Offer #{result['trade_id']}", description=f"{interaction.user.mention} offers **#{a['instance_id']} {a['name']}** ({a['rarity']}, OVR {a['ovr']})\nfor **#{b['instance_id']} {b['name']}** ({b['rarity']}, OVR {b['ovr']}) from {member.mention}.\n\n{member.mention}, use /trade accept with ID {result['trade_id']} to accept or /trade cancel with the same ID to decline. Expires in 24 hours.", color=discord.Color.dark_red())
    await interaction.response.send_message(content=member.mention, embed=embed)

@trades.command(name="incoming", description="View your pending incoming trade offers")
async def trade_incoming(interaction: discord.Interaction):
    if interaction.guild_id is None:
        await interaction.response.send_message("Use trading in the OG Clan server.", ephemeral=True)
        return
    offers = store.get_incoming_trades(interaction.guild_id, interaction.user.id)
    if not offers:
        await interaction.response.send_message("You have no pending trade offers.", ephemeral=True)
        return
    lines = [f"**#{t['trade_id']}** from <@{t['proposer_id']}>: **{t['offered_name']}** ({t['offered_rarity']}, OVR {t['offered_ovr']}) for your **{t['requested_name']}** ({t['requested_rarity']}, OVR {t['requested_ovr']}) — expires {t['expires_at']} UTC" for t in offers]
    await interaction.response.send_message("\n".join(lines), ephemeral=True)

@trades.command(name="accept", description="Accept an incoming card-for-card trade")
@app_commands.describe(trade_id="Trade offer number")
async def trade_accept(interaction: discord.Interaction, trade_id: app_commands.Range[int, 1, 100000000]):
    if interaction.guild_id is None:
        await interaction.response.send_message("Use trading in the OG Clan server.", ephemeral=True)
        return
    try:
        result = store.accept_trade(interaction.guild_id, trade_id, interaction.user.id)
    except ValueError as exc:
        await interaction.response.send_message(str(exc), ephemeral=True)
        return
    a, b = result["proposer_card"], result["recipient_card"]
    await interaction.response.send_message(f"**Trade #{trade_id} completed!** <@{result['proposer_id']}> received **{b['name']}** (card #{b['instance_id']}) and <@{result['recipient_id']}> received **{a['name']}** (card #{a['instance_id']}).")

@trades.command(name="cancel", description="Cancel your outgoing offer or decline an incoming offer")
@app_commands.describe(trade_id="Trade offer number")
async def trade_cancel(interaction: discord.Interaction, trade_id: app_commands.Range[int, 1, 100000000]):
    if interaction.guild_id is None:
        await interaction.response.send_message("Use trading in the OG Clan server.", ephemeral=True)
        return
    try:
        status = store.close_trade(interaction.guild_id, trade_id, interaction.user.id, decline=True)
    except ValueError as exc:
        await interaction.response.send_message(str(exc), ephemeral=True)
        return
    await interaction.response.send_message(f"Trade **#{trade_id}** {status}.", ephemeral=True)

@trades.command(name="history", description="View your recent trade history")
async def trade_history(interaction: discord.Interaction):
    if interaction.guild_id is None:
        await interaction.response.send_message("Use trading in the OG Clan server.", ephemeral=True)
        return
    history = store.get_trade_history(interaction.guild_id, interaction.user.id)
    if not history:
        await interaction.response.send_message("You have no trade history yet.", ephemeral=True)
        return
    lines = [f"**#{t['trade_id']}** with <@{t['recipient_id'] if t['proposer_id'] == interaction.user.id else t['proposer_id']}> — **{t['status']}**" for t in history]
    await interaction.response.send_message("\n".join(lines), ephemeral=True)

@admin.command(name="add-points", description="Credit newly earned points to a member and record an audit entry")
@admin_check()
@app_commands.describe(member="Member to credit", amount="New points earned", reason="Reason or source reference")
async def add_points(interaction: discord.Interaction, member: discord.Member, amount: app_commands.Range[int, 1, 10000000], reason: str):
    if interaction.guild_id is None:
        await interaction.response.send_message("Use this command in the OG Clan server.", ephemeral=True)
        return
    earned = store.credit_points(interaction.guild_id, member.id, amount, interaction.user.id, reason[:300])
    p = store.get_profile(interaction.guild_id, member.id)
    await interaction.response.send_message(
        f"Credited **{amount:,}** new points to {member.mention}. Packs earned: **{earned}**. "
        f"Unopened packs: **{p['packs']}**. Audit entry recorded.", ephemeral=True)



@admin.command(name="audit-recent", description="View recent point credits")
@admin_check()
async def audit_recent(interaction: discord.Interaction):
    entries = store.get_recent_audit(interaction.guild_id)
    if not entries:
        await interaction.response.send_message("No point credits recorded yet.", ephemeral=True)
        return
    lines = [f"• <@{e['user_id']}> +{e['amount']:,} by <@{e['actor_id']}> — {e['reason']}" for e in entries]
    await interaction.response.send_message("**Recent OG Cards point credits**\n" + "\n".join(lines), ephemeral=True)


@bot.tree.error
async def on_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CheckFailure):
        message = str(error) or "You don't have permission to use that command."
    else:
        print(f"Slash command error: {error!r}")
        message = "That command failed. Please try again; the error was logged."
    if interaction.response.is_done():
        await interaction.followup.send(message, ephemeral=True)
    else:
        await interaction.response.send_message(message, ephemeral=True)


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("DISCORD_TOKEN is missing. Copy .env.example to .env and set your bot token.")
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    bot.run(TOKEN)
