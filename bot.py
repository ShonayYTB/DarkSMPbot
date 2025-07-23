import discord
import json
import os
import random
import logging
from discord.ext import tasks
from discord import app_commands
from mcstatus import JavaServer
from datetime import datetime
import pytz

TOKEN = "MTM5NzM0Mzg2NjY5MjA0Njg2OA.GuBQHE.dCLczMWKWwgwTu4o0VUhr7zyHaWYNRDBE08DHM"
SERVER_IP = "88.211.207.236"
PORT = 25576
TIMEZONE = "Europe/Paris"
DATA_FOLDER = "minecraft_data"

VALID_CATEGORIES = [
    "tools", "blocks", "ores", "armor",
    "food", "dyes", "mobs", "potions",
    "utility", "enchantments", "recipes",
    "stations", "biomes"
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)

class MyClient(discord.Client):
    def __init__(self, *, intents):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.mode_label = "fast (15s)"

    async def setup_hook(self):
        await self.tree.sync()
        logging.info("✅ Slash commands synced.")

intents = discord.Intents.default()
client = MyClient(intents=intents)

@client.tree.command(name="hello", description="Say hi to the bot")
async def hello_command(interaction: discord.Interaction):
    logging.info(f"/hello used by {interaction.user} (ID: {interaction.user.id})")
    responses = [
        "Hi :)", "Meow :P", "GET OU–", "Shut yo",
        "You are now banned (just kidding)", "Well hello there.",
        "⛏ I'm mining your data... kidding.", "404: Greeting not found.", "You again? ", "HELP?", "LEAVE ME ALONE", "UwU"
    ]
    await interaction.response.send_message(random.choice(responses))

@client.tree.command(name="mode", description="Check if bot is in fast or slow update mode")
async def mode_command(interaction: discord.Interaction):
    logging.info(f"/mode used by {interaction.user} (ID: {interaction.user.id})")
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    await interaction.response.send_message(
        f"🕒 Server time: {now.strftime('%H:%M')}\n📡 Bot update mode: **{client.mode_label}**"
    )

@client.tree.command(name="update", description="Manually refresh Minecraft server status")
async def update_command(interaction: discord.Interaction):
    logging.info(f"/update used by {interaction.user} (ID: {interaction.user.id})")
    await interaction.response.defer()
    try:
        server = JavaServer.lookup(f"{SERVER_IP}:{PORT}")
        status = server.status()
        await client.change_presence(
            status=discord.Status.online,
            activity=discord.Game(name=f"{status.players.online}/{status.players.max} players online")
        )
        await interaction.followup.send("✅ Server status updated.")
    except:
        await client.change_presence(
            status=discord.Status.dnd,
            activity=discord.Game(name="Server offline")
        )
        await interaction.followup.send("⚠️ Server unreachable.")

@client.tree.command(name="wiki", description="Browse Minecraft encyclopedia")
async def wiki_command(interaction: discord.Interaction):
    logging.info(f"/wiki used by {interaction.user} (ID: {interaction.user.id})")
    view = CategorySelectView()
    embed = discord.Embed(
        title="📚 Minecraft Wiki",
        description="Select a category to explore.",
        color=discord.Color.orange()
    )
    await interaction.response.send_message(embed=embed, view=view)

class CategorySelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)
        options = [discord.SelectOption(label=cat.title(), value=cat) for cat in VALID_CATEGORIES]
        self.select = discord.ui.Select(placeholder="Select a category...", options=options)
        self.select.callback = self.category_selected
        self.add_item(self.select)

    async def category_selected(self, interaction: discord.Interaction):
        category = self.select.values[0]
        path = os.path.join(DATA_FOLDER, category, "data.json")
        if not os.path.exists(path):
            await interaction.response.send_message(f"❌ Missing file: `{category}/data.json`.", ephemeral=True)
            return

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        options = [
            discord.SelectOption(label=data[k].get("title", k.title())[:100], value=k)
            for k in data
        ]

        new_view = EntrySelectView(category, data)
        new_view.select.options = options

        embed = discord.Embed(
            title=f"📁 {category.title()}",
            description="Select an item to view details.",
            color=discord.Color.blue()
        )
        await interaction.response.edit_message(embed=embed, view=new_view)

class EntrySelectView(discord.ui.View):
    def __init__(self, category, data):
        super().__init__(timeout=120)
        self.category = category
        self.data = data
        self.select = discord.ui.Select(placeholder="Select an item...", options=[])
        self.select.callback = self.entry_selected
        self.add_item(self.select)

    async def entry_selected(self, interaction: discord.Interaction):
        key = self.select.values[0]
        entry = self.data[key]
        logging.info(f"Wiki entry selected: {key} by {interaction.user} (Category: {self.category})")

        embed = discord.Embed(
            title=entry.get("title", key.title()),
            description=f"📘 Category: {self.category.title()}",
            color=discord.Color.green()
        )
        image_url = entry.get("crafting_grid_url")
        if not image_url and self.category in ["recipes", "tools", "armor", "utility"]:
            slug = key.lower().replace(" ", "_")
            image_url = f"https://minecraft.wiki/images/Crafting_{slug}.png"

        for field, value in entry.items():
            if field != "title" and field != "crafting_grid_url":
                embed.add_field(name=field.replace("_", " ").title(), value=str(value), inline=False)

        if image_url:
            embed.set_image(url=image_url)
            embed.add_field(name="🧰 Crafting Grid", value=f"[Open image externally]({image_url})", inline=False)

        await interaction.response.edit_message(embed=embed, view=None)


@tasks.loop(seconds=15)
async def update_status():
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    hour = now.hour
    if 0 <= hour < 8:
        update_status.change_interval(seconds=60)
        client.mode_label = "slow (60s)"
    else:
        update_status.change_interval(seconds=15)
        client.mode_label = "fast (15s)"
    try:
        server = JavaServer.lookup(f"{SERVER_IP}:{PORT}")
        status = server.status()
        await client.change_presence(
            status=discord.Status.online,
            activity=discord.Game(name=f"{status.players.online}/{status.players.max} players online")
        )
    except:
        await client.change_presence(
            status=discord.Status.dnd,
            activity=discord.Game(name="Server offline")
        )

@client.event
async def on_ready():
    update_status.start()
    logging.info(f"✅ Bot ready as {client.user}")

client.run(TOKEN)