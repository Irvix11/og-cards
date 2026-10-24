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
DB_PATH = os.getenv("DATABASE_PATH", "data/og_cards.sqlite3")
TEST_GUILD_ID = os.getenv("TEST_GUILD_ID", "").strip()
ADMIN_ROLE_IDS = {int(x.strip()) for x in os.getenv("ADMIN_ROLE_IDS", "").split(",") if x.strip().isdigit()}

bot = commands.Bot(command_prefix="!", intents=discord.Intents.default())
store = CardStore(DB_PATH)


def is_card_admin(interaction: discord.Interaction) -> bool:
    if interaction.guild is None or not isinstance(interaction.user, discord.Member):
        return False
    return interaction.user.guild_permissions.administrator or any(r.id in ADMIN_ROLE_IDS for r in interaction.user.roles)


def admin_check():
    async def predicate(interaction: discord.Interaction) -> bool:
        if not is_card_admin(interaction):
            raise app_commands.CheckFailure("You need administrator permission or an approved OG Cards staff role.")
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
    embed = discord.Embed(title="OG CARD PACK OPENED", description=card_text(card), color=discord.Color.gold())
    embed.set_footer(text=f"{rarity} pull · Card instance #{card['instance_id']}")
    await interaction.response.send_message(embed=embed)


admin = app_commands.Group(name="admin", description="Staff-only OG Cards controls")
bot.tree.add_command(admin)


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
