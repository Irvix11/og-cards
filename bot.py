from __future__ import annotations

import asyncio
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



BRAND = "OG CLAN • CARD COLLECTION"
RARITY_COLOURS = {
    "Common": discord.Color.light_grey(),
    "Rare": discord.Color.blue(),
    "Epic": discord.Color.purple(),
    "Legendary": discord.Color.gold(),
    "Mythic": discord.Color.from_rgb(235, 35, 55),
}


def ui_embed(title: str, description: str = "", colour: discord.Color = discord.Color.dark_red()) -> discord.Embed:
    embed = discord.Embed(title=title, description=description, colour=colour)
    if bot.user:
        embed.set_author(name="OG CARDS", icon_url=bot.user.display_avatar.url)
    else:
        embed.set_author(name="OG CARDS")
    embed.set_footer(text=BRAND)
    return embed


def progress_bar(value: int, total: int, width: int = 14) -> str:
    filled = min(width, int(value / total * width)) if total else width
    return "▰" * filled + "▱" * (width - filled)


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
    embed = ui_embed(f"{interaction.user.display_name}'s Collection Profile", "Your OG Cards overview.", discord.Color.dark_red())
    embed.set_thumbnail(url=interaction.user.display_avatar.url)
    embed.add_field(name="Total Points", value=f"**{p['points_total']:,}**", inline=True)
    embed.add_field(name="Unopened Packs", value=f"**{p['packs']}**", inline=True)
    embed.add_field(name="Cards Owned", value=f"**{p['card_count']}**", inline=True)
    embed.add_field(name="Next Pack Progress", value=f"{progress_bar(p['progress'], POINTS_PER_PACK)}\n**{p['progress']:,} / {POINTS_PER_PACK:,}** points", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)


@cards.command(name="progress", description="Check your progress toward the next pack")
async def progress(interaction: discord.Interaction):
    p = store.get_profile(interaction.guild_id, interaction.user.id)
    embed = ui_embed("Pack Progress", "Keep earning OG points to unlock your next pack.")
    embed.add_field(name="Progress", value=f"{progress_bar(p['progress'], POINTS_PER_PACK)}\n**{p['progress']:,} / {POINTS_PER_PACK:,}**", inline=False)
    embed.add_field(name="Points Remaining", value=f"**{POINTS_PER_PACK-p['progress']:,}**", inline=True)
    embed.add_field(name="Ready to Open", value=f"**{p['packs']} pack(s)**", inline=True)
    await interaction.response.send_message(embed=embed, ephemeral=True)


@cards.command(name="collection", description="View a page of your collection or another member's")
@app_commands.describe(member="Optional member whose collection you want to view", page="Collection page (15 cards per page)")
async def collection(interaction: discord.Interaction, member: discord.Member | None = None, page: app_commands.Range[int, 1, 100] = 1):
    target = member or interaction.user
    total = store.count_cards(interaction.guild_id, target.id)
    items = store.get_collection(interaction.guild_id, target.id, limit=15, offset=(page - 1) * 15)
    if page > max(1, (total + 14) // 15):
        await interaction.response.send_message(f"That page doesn't exist. {target.display_name} has {total} card(s).", ephemeral=True)
        return
    embed = ui_embed(f"{target.display_name}'s Card Collection", f"Page **{page}** · **{total}** card(s) total")
    embed.set_thumbnail(url=target.display_avatar.url)
    if not items:
        embed.description = "No cards collected yet. Earn points, unlock a pack, and start building your collection."
    else:
        for card in items:
            embed.add_field(name=f"#{card['instance_id']} • {card['name']}", value=f"{card['rarity']}  ·  **OVR {card['ovr']}**\n{card['theme']} · {card['edition']}", inline=True)
    embed.set_footer(text=f"{BRAND}  •  Use /cards collection page:{page + 1} for the next page")
    await interaction.response.send_message(embed=embed, ephemeral=(member is None))


@cards.command(name="card", description="Inspect one of your cards by its instance ID")
@app_commands.describe(card_id="The # number shown in your collection")
async def card_detail(interaction: discord.Interaction, card_id: app_commands.Range[int, 1, 100000000]):
    card = store.get_card(interaction.guild_id, interaction.user.id, card_id)
    if card is None:
        await interaction.response.send_message("You don't own a card with that ID. Check /cards collection.", ephemeral=True)
        return
    colour = RARITY_COLOURS.get(card["rarity"], discord.Color.dark_red())
    embed = ui_embed(f"✦ {card['name']} ✦", f"**{card['rarity'].upper()}** · {card['theme']} · {card['edition']}", colour)
    embed.add_field(name="Overall Rating", value=f"**{card['ovr']} OVR**", inline=False)
    embed.add_field(name="Stats", value=f"PAC **{card['pac']}**  ·  ATK **{card['atk']}**  ·  DEF **{card['deff']}**  ·  SKL **{card['skl']}**", inline=False)
    embed.add_field(name="Card ID", value=f"**#{card['instance_id']}**", inline=True)
    embed.set_footer(text=f"{BRAND}  •  Card ownership is tied to this instance ID")
    await interaction.response.send_message(embed=embed, ephemeral=True)


@cards.command(name="catalogue", description="Browse the starter card catalogue")
async def catalogue(interaction: discord.Interaction):
    embed = ui_embed("OG Cards Catalogue", "Collect every rarity. Duplicate cards are allowed.")
    for card in STARTER_CARDS:
        embed.add_field(name=f"{card['rarity']} • {card['name']}", value=f"**OVR {card['ovr']}**  ·  {card['theme']}\nPAC {card['pac']}  ATK {card['atk']}  DEF {card['deff']}  SKL {card['skl']}", inline=True)
    embed.add_field(name="Pack Odds", value="Common 50% · Rare 27% · Epic 15% · Legendary 7% · Mythic 1%", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)


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
    colour = RARITY_COLOURS.get(rarity, discord.Color.dark_red())

    # Animated pack-opening sequence. The card is safely saved before the reveal starts.
    await interaction.response.defer(thinking=True)
    animation_frames = [
        ("▰━━━━━━━━━━━━━━▰", "A sealed OG pack appears...", discord.Color.dark_grey()),
        ("▰━━━━━━ ◈ ━━━━━━▰", "Scanning the pack for a signature...", discord.Color.dark_red()),
        ("▰━━━ ◈ ⚡ ◈ ━━━▰", "Energy levels rising. Something is inside.", discord.Color.from_rgb(150, 20, 35)),
        ("✦  SIGNATURE LOCKED  ✦", f"**{rarity.upper()}** signature detected. Preparing reveal...", colour),
    ]
    for index, (title, description, frame_colour) in enumerate(animation_frames):
        frame = ui_embed(f"〔 OG PACK OPENING 〕  {title}", description, frame_colour)
        frame.set_thumbnail(url=interaction.user.display_avatar.url)
        frame.set_footer(text=f"{BRAND}  •  Reveal sequence {index + 1}/{len(animation_frames)}")
        await interaction.edit_original_response(embed=frame)
        await asyncio.sleep(0.9 if index < 3 else 1.1)

    embed = ui_embed("✦ CARD DISCOVERED ✦", card_text(card), colour)
    embed.add_field(name="Card Number", value=f"**#{card['instance_id']}**", inline=True)
    embed.add_field(name="Rarity", value=f"**{rarity.upper()}**", inline=True)
    embed.add_field(name="Collection", value="Use `/cards collection` to view your cards.", inline=False)
    embed.set_thumbnail(url=interaction.user.display_avatar.url)
    embed.set_footer(text=f"{BRAND}  •  New card added to your collection")
    await interaction.edit_original_response(embed=embed)
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
    embed.set_footer(text=f"{BRAND}  •  Offer expires in 24 hours")
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
    embed = ui_embed("Incoming Trade Offers", "Review each offer carefully before accepting.")
    for offer in offers:
        embed.add_field(name=f"Offer #{offer['trade_id']} • From <@{offer['proposer_id']}>", value=f"**They give:** {offer['offered_name']} · {offer['offered_rarity']} · OVR {offer['offered_ovr']}\n**They want:** {offer['requested_name']} · {offer['requested_rarity']} · OVR {offer['requested_ovr']}\nExpires: {offer['expires_at']} UTC", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

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
    embed = ui_embed(f"✓ Trade #{trade_id} Completed", "Both cards have been transferred successfully.", discord.Color.green())
    embed.add_field(name=f"<@{result['proposer_id']}> received", value=f"**{b['name']}**\n{b['rarity']} · OVR {b['ovr']} · Card #{b['instance_id']}", inline=True)
    embed.add_field(name=f"<@{result['recipient_id']}> received", value=f"**{a['name']}**\n{a['rarity']} · OVR {a['ovr']} · Card #{a['instance_id']}", inline=True)
    await interaction.response.send_message(embed=embed)

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
