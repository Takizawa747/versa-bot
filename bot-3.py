import discord
from discord.ext import commands
from discord import app_commands
import yt_dlp
import asyncio
from collections import deque
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import json
import os
import requests
from datetime import timedelta, datetime
import random
import math

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix=".", intents=intents, help_command=None)

OWNER_ID = 1365571735222747280

guild_data = {}
afk_db = {}
xp_cooldown = {}
active_bj = {}

def is_owner(user_id):
    return user_id == OWNER_ID

PLAYLISTS_FILE = "playlists.json"
MODLOGS_FILE = "modlogs.json"
LEVELS_FILE = "levels.json"
GIVEAWAYS_FILE = "giveaways.json"
ECONOMY_FILE = "economy.json"
SETTINGS_FILE = "settings.json"

def load_json(path):
    if os.path.exists(path):
        with open(path, 'r') as f:
            return json.load(f)
    return {}

def save_json(path, data):
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)

playlists_db = load_json(PLAYLISTS_FILE)
modlogs_db = load_json(MODLOGS_FILE)
levels_db = load_json(LEVELS_FILE)
giveaways_db = load_json(GIVEAWAYS_FILE)
economy_db = load_json(ECONOMY_FILE)
settings_db = load_json(SETTINGS_FILE)

def get_settings(guild_id):
    gid = str(guild_id)
    if gid not in settings_db:
        settings_db[gid] = {'log': None, 'ticket': None, 'levelup': None, 'welcome': None}
    return settings_db[gid]

def save_settings():
    save_json(SETTINGS_FILE, settings_db)

ACTION_EMOJIS = {
    'kick': '👢', 'ban': '🔨', 'unban': '✅', 'timeout': '🔇',
    'untimeout': '🔊', 'mute': '🔇', 'unmute': '🔊', 'softban': '🔨',
}

def get_econ(guild_id, user_id):
    gid = str(guild_id)
    uid = str(user_id)
    if gid not in economy_db:
        economy_db[gid] = {}
    if uid not in economy_db[gid]:
        economy_db[gid][uid] = {'wallet': 500, 'bank': 0, 'last_daily': None, 'last_work': None}
    return economy_db[gid][uid]

def save_econ():
    save_json(ECONOMY_FILE, economy_db)

SUITS = ['♠️', '♥️', '♦️', '♣️']
RANKS = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']

def make_deck():
    deck = []
    for suit in SUITS:
        for rank in RANKS:
            deck.append({'rank': rank, 'suit': suit})
    random.shuffle(deck)
    return deck

def card_value(card):
    if card['rank'] in ['J', 'Q', 'K']:
        return 10
    if card['rank'] == 'A':
        return 11
    return int(card['rank'])

def hand_value(hand):
    total = sum(card_value(c) for c in hand)
    aces = sum(1 for c in hand if c['rank'] == 'A')
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total

def hand_str(hand, hide_second=False):
    if hide_second and len(hand) > 1:
        return f"`{hand[0]['rank']}{hand[0]['suit']}` 🂠"
    return " ".join(f"`{c['rank']}{c['suit']}`" for c in hand)

def is_soft(hand):
    total = sum(card_value(c) for c in hand)
    aces = sum(1 for c in hand if c['rank'] == 'A')
    if aces and total <= 21:
        hard = total - 10
        return hard != total
    return False

def log_case(guild_id, action, target, moderator, reason, duration=None):
    gid = str(guild_id)
    if gid not in modlogs_db:
        modlogs_db[gid] = {'counter': 0, 'cases': []}
    modlogs_db[gid]['counter'] += 1
    case_id = modlogs_db[gid]['counter']
    modlogs_db[gid]['cases'].append({
        'case_id': case_id, 'action': action,
        'target_id': target.id, 'target_tag': str(target),
        'moderator_id': moderator.id, 'moderator_tag': str(moderator),
        'reason': reason, 'duration': duration,
        'timestamp': datetime.utcnow().isoformat()
    })
    save_json(MODLOGS_FILE, modlogs_db)
    return case_id

def get_user_cases(guild_id, user_id):
    gid = str(guild_id)
    if gid not in modlogs_db:
        return []
    return [c for c in modlogs_db[gid]['cases'] if c['target_id'] == user_id]

def get_case_by_id(guild_id, case_id):
    gid = str(guild_id)
    if gid not in modlogs_db:
        return None
    for c in modlogs_db[gid]['cases']:
        if c['case_id'] == case_id:
            return c
    return None

def get_level(xp):
    return int(math.sqrt(xp / 100))

def xp_for_level(level):
    return level * level * 100

def get_user_data(guild_id, user_id):
    gid = str(guild_id)
    uid = str(user_id)
    if gid not in levels_db:
        levels_db[gid] = {}
    if uid not in levels_db[gid]:
        levels_db[gid][uid] = {'xp': 0, 'level': 0}
    return levels_db[gid][uid]

sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
    client_id="96a252f093924b46ad6e80d8ec4cbfc8",
    client_secret="66be642f3867485386a7b459db584c09"
))

ytdl_options = {
    'format': 'bestaudio/best', 'noplaylist': True,
    'quiet': True, 'no_warnings': True,
    'default_search': 'ytsearch', 'source_address': '0.0.0.0',
}
ffmpeg_options = {
    'options': '-vn',
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'
}
ytdl = yt_dlp.YoutubeDL(ytdl_options)

def get_guild_data(guild_id):
    if guild_id not in guild_data:
        guild_data[guild_id] = {
            'queue': deque(), 'loop': False, 'current': None,
            'panel': None, 'muted': False, 'prev_vol': 0.5, 'dj': None,
        }
    return guild_data[guild_id]

def fmt_duration(s):
    if not s:
        return "00:00"
    m, s = divmod(int(s), 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"

def resolve_query(query):
    if 'spotify.com/track' in query:
        track_id = query.split('/track/')[1].split('?')[0]
        track = sp.track(track_id)
        return f"{track['name']} {track['artists'][0]['name']}"
    return query

async def get_source(query):
    loop = asyncio.get_event_loop()
    resolved = await loop.run_in_executor(None, lambda: resolve_query(query))
    data = await loop.run_in_executor(None, lambda: ytdl.extract_info(resolved, download=False))
    if 'entries' in data:
        entries = list(data['entries'])
        if not entries:
            raise Exception("No results found!")
        data = entries[0]
    source = discord.FFmpegPCMAudio(data['url'], **ffmpeg_options)
    player = discord.PCMVolumeTransformer(source, volume=0.5)
    player.title = data.get('title', 'Unknown')
    player.duration = data.get('duration', 0)
    player.thumbnail = data.get('thumbnail')
    player.webpage_url = data.get('webpage_url')
    player.query = query
    return player

def get_lyrics(title):
    clean = title
    for w in ['(Official Video)', '(Official Music Video)', '(Lyric Video)', '(Audio)', 'Official Video']:
        clean = clean.replace(w, '').strip()
    parts = clean.split(' - ', 1)
    try:
        if len(parts) == 2:
            url = f"https://api.lyrics.ovh/v1/{parts[0].strip()}/{parts[1].strip()}"
            r = requests.get(url, timeout=8)
            if r.status_code == 200:
                d = r.json()
                if d.get('lyrics'):
                    return d['lyrics']
    except:
        pass
    return None

async def send_log(guild, embed):
    s = get_settings(guild.id)
    if not s.get('log'):
        return
    channel = guild.get_channel(int(s['log']))
    if channel is None:
        try:
            channel = await bot.fetch_channel(int(s['log']))
        except:
            return
    try:
        await channel.send(embed=embed)
    except:
        pass

async def post_case_log(guild, case_id, action, target, moderator, reason, duration=None):
    emoji = ACTION_EMOJIS.get(action, '📌')
    embed = discord.Embed(title=f"{emoji} Case #{case_id} — {action.title()}", color=0xff6b35, timestamp=datetime.utcnow())
    embed.add_field(name="Target", value=f"{target} (`{target.id}`)", inline=False)
    embed.add_field(name="Moderator", value=f"{moderator} (`{moderator.id}`)", inline=False)
    if duration:
        embed.add_field(name="Duration", value=f"{duration} minutes", inline=True)
    embed.add_field(name="Reason", value=reason, inline=False)
    try:
        embed.set_thumbnail(url=target.display_avatar.url)
    except:
        pass
    await send_log(guild, embed)

async def get_muted_role(guild):
    role = discord.utils.get(guild.roles, name="Muted")
    if role is None:
        role = await guild.create_role(name="Muted")
        for channel in guild.channels:
            try:
                if isinstance(channel, discord.TextChannel):
                    await channel.set_permissions(role, send_messages=False, add_reactions=False)
                elif isinstance(channel, discord.VoiceChannel):
                    await channel.set_permissions(role, speak=False)
            except:
                pass
    return role

def can_act_on(actor, target, guild):
    if is_owner(actor.id):
        return target.id != actor.id
    if target.id == guild.owner_id:
        return False
    if actor.id == guild.owner_id:
        return True
    return target.top_role < actor.top_role

async def update_panel(ctx_or_interaction, guild, voice_client, is_channel=False):
    data = get_guild_data(guild.id)
    cur = data.get('current')
    if not cur:
        return
    embed = discord.Embed(color=0xff6b35)
    embed.set_author(name="🎵 Now Playing")
    embed.add_field(name="Track:", value=f"**{cur.title}**", inline=False)
    embed.add_field(name="Duration:", value=f"`{fmt_duration(cur.duration)}`", inline=True)
    embed.add_field(name="Loop:", value="✅ On" if data['loop'] else "❌ Off", inline=True)
    embed.add_field(name="Queue:", value=f"`{len(data['queue'])} songs`", inline=True)
    if data.get('dj'):
        embed.add_field(name="🎧 DJ:", value=f"<@{data['dj']}>", inline=True)
    if cur.thumbnail:
        embed.set_thumbnail(url=cur.thumbnail)
    embed.set_footer(text="DJ controls freely • Others need to vote to skip/stop")
    view = MusicView(guild, voice_client, data.get('dj'))
    if data.get('panel'):
        try:
            await data['panel'].edit(embed=embed, view=view)
            return
        except:
            pass
    if is_channel:
        msg = await ctx_or_interaction.send(embed=embed, view=view)
    else:
        msg = await ctx_or_interaction.followup.send(embed=embed, view=view)
    data['panel'] = msg

async def play_next(guild, voice_client, ctx_or_interaction):
    data = get_guild_data(guild.id)
    if not voice_client or not voice_client.is_connected():
        return
    if data['loop'] and data['current']:
        try:
            source = await get_source(data['current'].webpage_url)
            data['current'] = source
            voice_client.play(source, after=lambda e: asyncio.run_coroutine_threadsafe(
                play_next(guild, voice_client, ctx_or_interaction), bot.loop))
            is_ch = not hasattr(ctx_or_interaction, 'followup')
            ch = ctx_or_interaction.channel if is_ch else ctx_or_interaction
            await update_panel(ch, guild, voice_client, is_channel=is_ch)
        except:
            pass
        return
    if data['queue']:
        source = data['queue'].popleft()
        data['current'] = source
        voice_client.play(source, after=lambda e: asyncio.run_coroutine_threadsafe(
            play_next(guild, voice_client, ctx_or_interaction), bot.loop))
        is_ch = not hasattr(ctx_or_interaction, 'followup')
        ch = ctx_or_interaction.channel if is_ch else ctx_or_interaction
        await update_panel(ch, guild, voice_client, is_channel=is_ch)
    else:
        data['current'] = None
        data['dj'] = None
        embed = discord.Embed(description="✅ Queue ended!", color=0xff6b35)
        if data.get('panel'):
            try:
                await data['panel'].edit(embed=embed, view=None)
            except:
                pass

class VoteView(discord.ui.View):
    def __init__(self, action, guild, voice_client, needed_votes):
        super().__init__(timeout=30)
        self.action = action
        self.guild = guild
        self.voice_client = voice_client
        self.needed_votes = needed_votes
        self.voters = set()

    @discord.ui.button(label="✅ Vote Yes", style=discord.ButtonStyle.green)
    async def vote_yes(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id in self.voters:
            await interaction.response.send_message("❌ You already voted!", ephemeral=True)
            return
        self.voters.add(interaction.user.id)
        count = len(self.voters)
        if count >= self.needed_votes:
            vc = self.voice_client
            if self.action == 'skip':
                if vc and (vc.is_playing() or vc.is_paused()):
                    vc.stop()
                await interaction.response.edit_message(content="⏭️ Vote passed! Skipped!", view=None)
            elif self.action == 'stop':
                data = get_guild_data(self.guild.id)
                data['queue'].clear()
                data['current'] = None
                data['dj'] = None
                if vc:
                    await vc.disconnect()
                await interaction.response.edit_message(content="⏹️ Vote passed! Stopped!", view=None)
        else:
            await interaction.response.edit_message(
                content=f"🗳️ **Vote to {self.action}!** ({count}/{self.needed_votes} votes)", view=self)

class MusicView(discord.ui.View):
    def __init__(self, guild, voice_client, dj_id=None):
        super().__init__(timeout=None)
        self.guild = guild
        self.voice_client = voice_client
        self.dj_id = dj_id

    def is_dj(self, user_id):
        return self.dj_id is None or user_id == self.dj_id

    def get_needed_votes(self):
        if self.voice_client and self.voice_client.channel:
            members = [m for m in self.voice_client.channel.members if not m.bot]
            return max(1, len(members) // 2)
        return 1

    @discord.ui.button(emoji="⏮️", style=discord.ButtonStyle.grey, row=0)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("❌ No previous track!", ephemeral=True)

    @discord.ui.button(emoji="⏸️", style=discord.ButtonStyle.grey, row=0)
    async def pause_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_dj(interaction.user.id):
            await interaction.response.send_message("❌ Only the DJ can pause/resume!", ephemeral=True)
            return
        await interaction.response.defer()
        vc = self.voice_client
        if vc:
            if vc.is_playing():
                vc.pause()
                button.emoji = "▶️"
            elif vc.is_paused():
                vc.resume()
                button.emoji = "⏸️"
            await interaction.message.edit(view=self)

    @discord.ui.button(emoji="⏭️", style=discord.ButtonStyle.grey, row=0)
    async def skip_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.is_dj(interaction.user.id):
            await interaction.response.defer()
            vc = self.voice_client
            if vc and (vc.is_playing() or vc.is_paused()):
                vc.stop()
        else:
            needed = self.get_needed_votes()
            await interaction.response.send_message(
                f"🗳️ **Vote to skip!** (0/{needed} votes)",
                view=VoteView('skip', self.guild, self.voice_client, needed))

    @discord.ui.button(emoji="🔇", style=discord.ButtonStyle.grey, row=1)
    async def mute_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_dj(interaction.user.id):
            await interaction.response.send_message("❌ Only the DJ can mute!", ephemeral=True)
            return
        await interaction.response.defer()
        vc = self.voice_client
        data = get_guild_data(self.guild.id)
        if vc and vc.source:
            if not data['muted']:
                data['prev_vol'] = vc.source.volume
                vc.source.volume = 0
                data['muted'] = True
                button.emoji = "🔊"
            else:
                vc.source.volume = data['prev_vol']
                data['muted'] = False
                button.emoji = "🔇"
            await interaction.message.edit(view=self)

    @discord.ui.button(emoji="🔉", style=discord.ButtonStyle.grey, row=1)
    async def vol_down_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_dj(interaction.user.id):
            await interaction.response.send_message("❌ Only the DJ can change volume!", ephemeral=True)
            return
        await interaction.response.defer()
        vc = self.voice_client
        if vc and vc.source:
            vc.source.volume = max(0.0, vc.source.volume - 0.1)

    @discord.ui.button(emoji="🔊", style=discord.ButtonStyle.grey, row=1)
    async def vol_up_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_dj(interaction.user.id):
            await interaction.response.send_message("❌ Only the DJ can change volume!", ephemeral=True)
            return
        await interaction.response.defer()
        vc = self.voice_client
        if vc and vc.source:
            vc.source.volume = min(1.0, vc.source.volume + 0.1)

    @discord.ui.button(emoji="📋", style=discord.ButtonStyle.grey, row=2)
    async def queue_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = get_guild_data(self.guild.id)
        q = data['queue']
        if not q:
            await interaction.response.send_message("📋 Queue is empty!", ephemeral=True)
            return
        msg = "📋 **Queue:**\n"
        for i, s in enumerate(q, 1):
            msg += f"`{i}.` {s.title}\n"
        await interaction.response.send_message(msg, ephemeral=True)

    @discord.ui.button(emoji="💾", style=discord.ButtonStyle.grey, row=2)
    async def save_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = get_guild_data(self.guild.id)
        cur = data.get('current')
        if cur:
            await interaction.response.send_message(f"🔗 **{cur.title}**\n{cur.webpage_url}", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Nothing playing!", ephemeral=True)

    @discord.ui.button(emoji="🔁", style=discord.ButtonStyle.grey, row=2)
    async def loop_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_dj(interaction.user.id):
            await interaction.response.send_message("❌ Only the DJ can toggle loop!", ephemeral=True)
            return
        await interaction.response.defer()
        data = get_guild_data(self.guild.id)
        data['loop'] = not data['loop']
        button.style = discord.ButtonStyle.green if data['loop'] else discord.ButtonStyle.grey
        await interaction.message.edit(view=self)

    @discord.ui.button(emoji="⏹️", style=discord.ButtonStyle.red, row=3)
    async def stop_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.is_dj(interaction.user.id):
            await interaction.response.defer()
            data = get_guild_data(self.guild.id)
            data['queue'].clear()
            data['current'] = None
            data['dj'] = None
            vc = self.voice_client
            if vc:
                await vc.disconnect()
        else:
            needed = self.get_needed_votes()
            await interaction.response.send_message(
                f"🗳️ **Vote to stop!** (0/{needed} votes)",
                view=VoteView('stop', self.guild, self.voice_client, needed))

class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🎫 Create Ticket", style=discord.ButtonStyle.blurple, custom_id="create_ticket_btn")
    async def create_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        safe_name = interaction.user.name.lower().replace(' ', '-')[:20]
        existing = discord.utils.get(interaction.guild.text_channels, name=f"ticket-{safe_name}")
        if existing:
            await interaction.response.send_message(f"❌ You already have an open ticket: {existing.mention}", ephemeral=True)
            return
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True),
            interaction.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True),
        }
        for role in interaction.guild.roles:
            if role.permissions.manage_messages and not role.is_default():
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        channel = await interaction.guild.create_text_channel(
            f"ticket-{safe_name}", overwrites=overwrites,
            reason=f"Ticket by {interaction.user}"
        )
        embed = discord.Embed(
            title="🎫 Support Ticket",
            description=f"Hello {interaction.user.mention}! 👋\n\nPlease describe your issue and staff will assist you shortly.\n\nClick below to close the ticket.",
            color=0xff6b35, timestamp=datetime.utcnow()
        )
        embed.set_footer(text=f"Opened by {interaction.user}")
        await channel.send(embed=embed, view=CloseTicketView())
        await interaction.response.send_message(f"✅ Your ticket: {channel.mention}", ephemeral=True)
        log_embed = discord.Embed(description=f"🎫 **Ticket created** by {interaction.user.mention} → {channel.mention}", color=0x00ff66, timestamp=datetime.utcnow())
        await send_log(interaction.guild, log_embed)

class CloseTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔒 Close Ticket", style=discord.ButtonStyle.red, custom_id="close_ticket_btn")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(description=f"🔒 Closing in 5 seconds... (by {interaction.user.mention})", color=0xff3333)
        await interaction.response.send_message(embed=embed)
        log_embed = discord.Embed(description=f"🔒 **Ticket closed:** #{interaction.channel.name}\nBy: {interaction.user}", color=0xff3333, timestamp=datetime.utcnow())
        await send_log(interaction.guild, log_embed)
        await asyncio.sleep(5)
        try:
            await interaction.channel.delete(reason=f"Ticket closed by {interaction.user}")
        except:
            pass

class GiveawayView(discord.ui.View):
    def __init__(self, giveaway_id):
        super().__init__(timeout=None)
        self.giveaway_id = str(giveaway_id)

    @discord.ui.button(label="🎉 Enter Giveaway", style=discord.ButtonStyle.green, custom_id="enter_giveaway_btn")
    async def enter(self, interaction: discord.Interaction, button: discord.ui.Button):
        gid = str(interaction.guild.id)
        if gid not in giveaways_db or self.giveaway_id not in giveaways_db[gid]:
            await interaction.response.send_message("❌ Giveaway not found!", ephemeral=True)
            return
        ga = giveaways_db[gid][self.giveaway_id]
        if ga.get('ended'):
            await interaction.response.send_message("❌ This giveaway has ended!", ephemeral=True)
            return
        uid = str(interaction.user.id)
        if uid in ga['participants']:
            ga['participants'].remove(uid)
            save_json(GIVEAWAYS_FILE, giveaways_db)
            await interaction.response.send_message(f"❌ You left the giveaway! Entries: {len(ga['participants'])}", ephemeral=True)
        else:
            ga['participants'].append(uid)
            save_json(GIVEAWAYS_FILE, giveaways_db)
            await interaction.response.send_message(f"✅ You entered! Entries: {len(ga['participants'])}", ephemeral=True)
        if interaction.message.embeds:
            emb = interaction.message.embeds[0]
            new_emb = discord.Embed(title=emb.title, description=emb.description, color=emb.color, timestamp=emb.timestamp)
            for field in emb.fields:
                if field.name == "Entries":
                    new_emb.add_field(name="Entries", value=f"`{len(ga['participants'])}`", inline=True)
                else:
                    new_emb.add_field(name=field.name, value=field.value, inline=field.inline)
            new_emb.set_footer(text=emb.footer.text if emb.footer else "")
            try:
                await interaction.message.edit(embed=new_emb)
            except:
                pass

class BlackjackView(discord.ui.View):
    def __init__(self, guild_id, user_id, bet):
        super().__init__(timeout=60)
        self.guild_id = guild_id
        self.user_id = user_id
        self.bet = bet

    async def update_game(self, interaction, ended=False):
        key = f"{self.guild_id}_{self.user_id}"
        game = active_bj.get(key)
        if not game:
            return
        pval = hand_value(game['player'])
        dval = hand_value(game['dealer'])
        embed = discord.Embed(title="🃏 Blackjack", color=0xff6b35)
        embed.add_field(name=f"{interaction.user.display_name}'s Hand", value=f"{hand_str(game['player'])}\nValue: {'Soft ' if is_soft(game['player']) else ''}{pval}", inline=False)
        if ended:
            embed.add_field(name="Dealer Hand", value=f"{hand_str(game['dealer'])}\nValue: {dval}", inline=False)
        else:
            embed.add_field(name="Dealer Hand", value=f"{hand_str(game['dealer'], hide_second=True)}\nValue: {hand_value([game['dealer'][0]])}", inline=False)
        embed.add_field(name="Cards Remaining", value=f"`{len(game['deck'])}` remaining", inline=False)
        if ended:
            econ = get_econ(self.guild_id, self.user_id)
            if pval > 21:
                result = f"💥 Bust! You lost **${self.bet:,}**!"
                color = 0xff3333
            elif dval > 21 or pval > dval:
                winnings = int(self.bet * 2)
                econ['wallet'] += winnings
                result = f"🎉 You win **${winnings:,}**!"
                color = 0x00ff66
            elif pval == dval:
                econ['wallet'] += self.bet
                result = f"🤝 Push! Bet returned **${self.bet:,}**!"
                color = 0xffaa00
            else:
                result = f"😢 Dealer wins! You lost **${self.bet:,}**!"
                color = 0xff3333
            save_econ()
            embed.color = color
            embed.add_field(name="Result", value=result, inline=False)
            embed.add_field(name="💰 Balance", value=f"${econ['wallet']:,}", inline=False)
            await interaction.response.edit_message(embed=embed, view=None)
            del active_bj[key]
        else:
            await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Hit", style=discord.ButtonStyle.blurple)
    async def hit(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ This is not your game!", ephemeral=True)
            return
        key = f"{self.guild_id}_{self.user_id}"
        game = active_bj[key]
        game['player'].append(game['deck'].pop())
        if hand_value(game['player']) >= 21:
            await self.dealer_play(interaction)
        else:
            await self.update_game(interaction)

    @discord.ui.button(label="Stand", style=discord.ButtonStyle.green)
    async def stand(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ This is not your game!", ephemeral=True)
            return
        await self.dealer_play(interaction)

    @discord.ui.button(label="Double Down", style=discord.ButtonStyle.grey)
    async def double_down(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ This is not your game!", ephemeral=True)
            return
        key = f"{self.guild_id}_{self.user_id}"
        game = active_bj[key]
        econ = get_econ(self.guild_id, self.user_id)
        if econ['wallet'] < self.bet:
            await interaction.response.send_message("❌ Not enough balance!", ephemeral=True)
            return
        econ['wallet'] -= self.bet
        save_econ()
        self.bet *= 2
        game['player'].append(game['deck'].pop())
        await self.dealer_play(interaction)

    @discord.ui.button(label="? Help", style=discord.ButtonStyle.grey)
    async def help_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="🃏 Blackjack Help", color=0xff6b35)
        embed.add_field(name="Hit", value="Draw another card", inline=False)
        embed.add_field(name="Stand", value="End your turn, dealer plays", inline=False)
        embed.add_field(name="Double Down", value="Double your bet, draw one card", inline=False)
        embed.add_field(name="Goal", value="Get closer to 21 than dealer without busting!", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def dealer_play(self, interaction):
        key = f"{self.guild_id}_{self.user_id}"
        game = active_bj[key]
        while hand_value(game['dealer']) < 17:
            game['dealer'].append(game['deck'].pop())
        await self.update_game(interaction, ended=True)

    async def on_timeout(self):
        key = f"{self.guild_id}_{self.user_id}"
        if key in active_bj:
            del active_bj[key]

async def end_giveaway(guild, gid, ga_id):
    if gid not in giveaways_db or ga_id not in giveaways_db[gid]:
        return
    ga = giveaways_db[gid][ga_id]
    if ga.get('ended'):
        return
    ga['ended'] = True
    save_json(GIVEAWAYS_FILE, giveaways_db)
    channel = bot.get_channel(int(ga['channel_id']))
    if not channel:
        return
    participants = ga['participants']
    if not participants:
        embed = discord.Embed(description=f"🎉 **{ga['prize']}** — No participants!", color=0x999999)
        try:
            msg = await channel.fetch_message(int(ga['message_id']))
            await msg.edit(embed=embed, view=None)
        except:
            await channel.send(embed=embed)
        return
    winners = random.sample(participants, min(ga['winners'], len(participants)))
    winner_mentions = " ".join(f"<@{w}>" for w in winners)
    embed = discord.Embed(title=f"🎉 GIVEAWAY ENDED: {ga['prize']}", description=f"**Winner(s):** {winner_mentions}", color=0xffd700)
    embed.add_field(name="Total Entries", value=f"`{len(participants)}`", inline=True)
    try:
        msg = await channel.fetch_message(int(ga['message_id']))
        await msg.edit(embed=embed, view=None)
    except:
        pass
    await channel.send(f"🎉 Congratulations {winner_mentions}! You won **{ga['prize']}**!")

@bot.event
async def on_ready():
    await bot.tree.sync()
    bot.add_view(TicketView())
    bot.add_view(CloseTicketView())
    print(f"{bot.user} is online! 🎵")
    try:
        for guild in bot.guilds:
            s = get_settings(guild.id)
            if s.get('ticket'):
                ticket_ch = bot.get_channel(int(s['ticket']))
                if ticket_ch:
                    async for msg in ticket_ch.history(limit=10):
                        if msg.author == bot.user and msg.embeds:
                            break
                    else:
                        embed = discord.Embed(
                            title="🎫 Support Tickets",
                            description="Need help? Click below to open a private support ticket!\nStaff will assist you as soon as possible.",
                            color=0xff6b35
                        )
                        await ticket_ch.send(embed=embed, view=TicketView())
    except:
        pass

@bot.event
async def on_message(message):
    if message.author.bot:
        await bot.process_commands(message)
        return
    if message.author.id in afk_db:
        del afk_db[message.author.id]
        try:
            await message.channel.send(f"👋 Welcome back {message.author.mention}, AFK removed!", delete_after=5)
        except:
            pass
    for mention in message.mentions:
        if mention.id in afk_db:
            data = afk_db[mention.id]
            try:
                await message.channel.send(f"💤 **{mention.display_name}** is AFK: {data['reason']}", delete_after=10)
            except:
                pass
    if message.guild:
        uid = str(message.author.id)
        gid = str(message.guild.id)
        now = datetime.utcnow().timestamp()
        cooldown_key = f"{gid}_{uid}"
        if cooldown_key not in xp_cooldown or now - xp_cooldown[cooldown_key] > 30:
            xp_cooldown[cooldown_key] = now
            udata = get_user_data(message.guild.id, message.author.id)
            old_level = get_level(udata['xp'])
            udata['xp'] += random.randint(10, 25)
            new_level = get_level(udata['xp'])
            udata['level'] = new_level
            save_json(LEVELS_FILE, levels_db)
            if new_level > old_level:
                s = get_settings(message.guild.id)
                if s.get('levelup'):
                    levelup_ch = bot.get_channel(int(s['levelup']))
                    if levelup_ch:
                        embed = discord.Embed(
                            description=f"🎉 {message.author.mention} reached **Level {new_level}**! 🚀",
                            color=0xff6b35
                        )
                        try:
                            await levelup_ch.send(embed=embed)
                        except:
                            pass
    await bot.process_commands(message)

@bot.event
async def on_member_join(member):
    embed = discord.Embed(description=f"📥 **{member}** joined the server", color=0x00ff66, timestamp=datetime.utcnow())
    embed.add_field(name="Account Created", value=member.created_at.strftime("%Y-%m-%d %H:%M UTC"), inline=False)
    embed.add_field(name="User ID", value=f"`{member.id}`", inline=False)
    embed.set_thumbnail(url=member.display_avatar.url)
    await send_log(member.guild, embed)
    s = get_settings(member.guild.id)
    welcome_ch_id = s.get('welcome')
    welcome_channel = member.guild.get_channel(int(welcome_ch_id)) if welcome_ch_id else member.guild.system_channel
    if welcome_channel:
        w_embed = discord.Embed(
            description=f"🎉 Welcome to **{member.guild.name}**, {member.mention}!\nYou are member #{member.guild.member_count}.",
            color=0xff6b35
        )
        w_embed.set_thumbnail(url=member.display_avatar.url)
        try:
            await welcome_channel.send(embed=w_embed)
        except:
            pass

@bot.event
async def on_member_remove(member):
    embed = discord.Embed(description=f"📤 **{member}** left the server", color=0x999999, timestamp=datetime.utcnow())
    embed.add_field(name="User ID", value=f"`{member.id}`", inline=False)
    if member.joined_at:
        embed.add_field(name="Joined At", value=member.joined_at.strftime("%Y-%m-%d %H:%M UTC"), inline=False)
    embed.set_thumbnail(url=member.display_avatar.url)
    await send_log(member.guild, embed)

@bot.event
async def on_member_update(before, after):
    if before.timed_out_until != after.timed_out_until:
        if after.timed_out_until is not None:
            embed = discord.Embed(description=f"🔇 **{after}** was timed out", color=0xff6b35, timestamp=datetime.utcnow())
            embed.add_field(name="Until", value=after.timed_out_until.strftime("%Y-%m-%d %H:%M UTC"), inline=False)
            embed.add_field(name="User ID", value=f"`{after.id}`", inline=False)
            try:
                await asyncio.sleep(0.5)
                async for entry in after.guild.audit_logs(action=discord.AuditLogAction.member_update, limit=1):
                    if entry.target.id == after.id:
                        embed.add_field(name="By", value=str(entry.user), inline=False)
                        if entry.reason:
                            embed.add_field(name="Reason", value=entry.reason, inline=False)
                        break
            except:
                pass
            await send_log(after.guild, embed)
        else:
            embed = discord.Embed(description=f"🔊 **{after}**'s timeout was removed", color=0x00ff66, timestamp=datetime.utcnow())
            embed.add_field(name="User ID", value=f"`{after.id}`", inline=False)
            try:
                await asyncio.sleep(0.5)
                async for entry in after.guild.audit_logs(action=discord.AuditLogAction.member_update, limit=1):
                    if entry.target.id == after.id:
                        embed.add_field(name="By", value=str(entry.user), inline=False)
                        break
            except:
                pass
            await send_log(after.guild, embed)

@bot.event
async def on_member_ban(guild, user):
    embed = discord.Embed(description=f"🔨 **{user}** was banned", color=0xff0000, timestamp=datetime.utcnow())
    embed.add_field(name="User ID", value=f"`{user.id}`", inline=False)
    try:
        await asyncio.sleep(0.5)
        async for entry in guild.audit_logs(action=discord.AuditLogAction.ban, limit=1):
            if entry.target.id == user.id:
                embed.add_field(name="By", value=str(entry.user), inline=False)
                embed.add_field(name="Reason", value=entry.reason or "No reason", inline=False)
                break
    except:
        pass
    await send_log(guild, embed)

@bot.event
async def on_member_unban(guild, user):
    embed = discord.Embed(description=f"✅ **{user}** was unbanned", color=0x00ff66, timestamp=datetime.utcnow())
    embed.add_field(name="User ID", value=f"`{user.id}`", inline=False)
    try:
        await asyncio.sleep(0.5)
        async for entry in guild.audit_logs(action=discord.AuditLogAction.unban, limit=1):
            if entry.target.id == user.id:
                embed.add_field(name="By", value=str(entry.user), inline=False)
                break
    except:
        pass
    await send_log(guild, embed)

@bot.event
async def on_message_delete(message):
    if message.author.bot or not message.guild:
        return
    embed = discord.Embed(description=f"🗑️ **Message deleted** in {message.channel.mention}", color=0xff3333, timestamp=datetime.utcnow())
    embed.add_field(name="Author", value=f"{message.author} (`{message.author.id}`)", inline=False)
    content = message.content if message.content else "*No cached content*"
    if len(content) > 1000:
        content = content[:1000] + "..."
    embed.add_field(name="Content", value=content, inline=False)
    if message.attachments:
        embed.add_field(name="Attachments", value=f"`{len(message.attachments)}` file(s)", inline=False)
    embed.set_footer(text=f"Message ID: {message.id}")
    await send_log(message.guild, embed)

@bot.event
async def on_bulk_message_delete(messages):
    if not messages or not messages[0].guild:
        return
    embed = discord.Embed(description=f"🗑️ **{len(messages)} messages** bulk deleted in {messages[0].channel.mention}", color=0xff3333, timestamp=datetime.utcnow())
    await send_log(messages[0].guild, embed)

@bot.event
async def on_message_edit(before, after):
    if before.author.bot or not before.guild or before.content == after.content:
        return
    embed = discord.Embed(description=f"✏️ **Message edited** in {before.channel.mention}", color=0xffaa00, timestamp=datetime.utcnow())
    embed.add_field(name="Author", value=f"{before.author} (`{before.author.id}`)", inline=False)
    old_c = (before.content or "*Empty*")[:500]
    new_c = (after.content or "*Empty*")[:500]
    embed.add_field(name="Before", value=old_c, inline=False)
    embed.add_field(name="After", value=new_c, inline=False)
    embed.add_field(name="Jump", value=f"[Click here]({after.jump_url})", inline=False)
    await send_log(before.guild, embed)

@bot.event
async def on_guild_channel_create(channel):
    embed = discord.Embed(description=f"📁 **Channel created:** #{channel.name}", color=0x00ff66, timestamp=datetime.utcnow())
    embed.add_field(name="Type", value=str(channel.type), inline=True)
    embed.add_field(name="ID", value=f"`{channel.id}`", inline=True)
    try:
        await asyncio.sleep(0.5)
        async for entry in channel.guild.audit_logs(action=discord.AuditLogAction.channel_create, limit=1):
            embed.add_field(name="Created by", value=str(entry.user), inline=False)
            break
    except:
        pass
    await send_log(channel.guild, embed)

@bot.event
async def on_guild_channel_delete(channel):
    embed = discord.Embed(description=f"🗑️ **Channel deleted:** #{channel.name}", color=0xff3333, timestamp=datetime.utcnow())
    embed.add_field(name="ID", value=f"`{channel.id}`", inline=True)
    try:
        await asyncio.sleep(0.5)
        async for entry in channel.guild.audit_logs(action=discord.AuditLogAction.channel_delete, limit=1):
            embed.add_field(name="Deleted by", value=str(entry.user), inline=False)
            break
    except:
        pass
    await send_log(channel.guild, embed)

@bot.event
async def on_guild_channel_update(before, after):
    changes = []
    if before.name != after.name:
        changes.append(f"**Name:** {before.name} → {after.name}")
    if hasattr(before, 'topic') and before.topic != after.topic:
        changes.append(f"**Topic:** {before.topic or '*None*'} → {after.topic or '*None*'}")
    if not changes:
        return
    embed = discord.Embed(description=f"✏️ **Channel updated:** #{after.name}", color=0xffaa00, timestamp=datetime.utcnow())
    embed.add_field(name="Changes", value="\n".join(changes), inline=False)
    try:
        await asyncio.sleep(0.5)
        async for entry in after.guild.audit_logs(action=discord.AuditLogAction.channel_update, limit=1):
            embed.add_field(name="Updated by", value=str(entry.user), inline=False)
            break
    except:
        pass
    await send_log(after.guild, embed)

@bot.event
async def on_guild_role_create(role):
    embed = discord.Embed(description=f"🎭 **Role created:** {role.name}", color=0x00ff66, timestamp=datetime.utcnow())
    embed.add_field(name="Color", value=str(role.color), inline=True)
    embed.add_field(name="ID", value=f"`{role.id}`", inline=True)
    try:
        await asyncio.sleep(0.5)
        async for entry in role.guild.audit_logs(action=discord.AuditLogAction.role_create, limit=1):
            embed.add_field(name="Created by", value=str(entry.user), inline=False)
            break
    except:
        pass
    await send_log(role.guild, embed)

@bot.event
async def on_guild_role_delete(role):
    embed = discord.Embed(description=f"🗑️ **Role deleted:** {role.name}", color=0xff3333, timestamp=datetime.utcnow())
    embed.add_field(name="ID", value=f"`{role.id}`", inline=True)
    try:
        await asyncio.sleep(0.5)
        async for entry in role.guild.audit_logs(action=discord.AuditLogAction.role_delete, limit=1):
            embed.add_field(name="Deleted by", value=str(entry.user), inline=False)
            break
    except:
        pass
    await send_log(role.guild, embed)

@bot.event
async def on_guild_role_update(before, after):
    changes = []
    if before.name != after.name:
        changes.append(f"**Name:** {before.name} → {after.name}")
    if before.color != after.color:
        changes.append(f"**Color:** {before.color} → {after.color}")
    if before.permissions != after.permissions:
        changes.append("**Permissions changed**")
    if not changes:
        return
    embed = discord.Embed(description=f"✏️ **Role updated:** {after.name}", color=0xffaa00, timestamp=datetime.utcnow())
    embed.add_field(name="Changes", value="\n".join(changes), inline=False)
    try:
        await asyncio.sleep(0.5)
        async for entry in after.guild.audit_logs(action=discord.AuditLogAction.role_update, limit=1):
            embed.add_field(name="Updated by", value=str(entry.user), inline=False)
            break
    except:
        pass
    await send_log(after.guild, embed)

@bot.event
async def on_guild_update(before, after):
    changes = []
    if before.name != after.name:
        changes.append(f"**Name:** {before.name} → {after.name}")
    if before.icon != after.icon:
        changes.append("**Icon changed**")
    if before.description != after.description:
        changes.append("**Description changed**")
    if not changes:
        return
    embed = discord.Embed(description="🏠 **Server updated**", color=0xffaa00, timestamp=datetime.utcnow())
    embed.add_field(name="Changes", value="\n".join(changes), inline=False)
    await send_log(after, embed)

# ========== SLASH COMMANDS ==========

@bot.tree.command(name="ping", description="Check bot latency")
async def ping_slash(interaction: discord.Interaction):
    embed = discord.Embed(title="🏓 Pong!", color=0xff6b35)
    embed.add_field(name="Latency", value=f"`{round(bot.latency * 1000)}ms`", inline=True)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="rank", description="Check your or someone's level")
@app_commands.describe(member="Member to check")
async def rank_slash(interaction: discord.Interaction, member: discord.Member = None):
    member = member or interaction.user
    udata = get_user_data(interaction.guild.id, member.id)
    xp = udata['xp']
    level = get_level(xp)
    embed = discord.Embed(title=f"📊 {member.display_name}'s Rank", color=0xff6b35)
    embed.add_field(name="Level", value=f"`{level}`", inline=True)
    embed.add_field(name="XP", value=f"`{xp}/{xp_for_level(level+1)}`", inline=True)
    embed.set_thumbnail(url=member.display_avatar.url)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="leaderboard", description="Show XP leaderboard")
async def leaderboard_slash(interaction: discord.Interaction):
    gid = str(interaction.guild.id)
    if gid not in levels_db or not levels_db[gid]:
        await interaction.response.send_message("❌ No data yet!")
        return
    sorted_users = sorted(levels_db[gid].items(), key=lambda x: x[1]['xp'], reverse=True)[:10]
    embed = discord.Embed(title="🏆 XP Leaderboard", color=0xff6b35)
    for i, (uid, data) in enumerate(sorted_users, 1):
        member = interaction.guild.get_member(int(uid))
        name = member.display_name if member else f"User {uid}"
        embed.add_field(name=f"{i}. {name}", value=f"Level `{get_level(data['xp'])}` • XP `{data['xp']}`", inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="afk", description="Set yourself as AFK")
@app_commands.describe(reason="Reason")
async def afk_slash(interaction: discord.Interaction, reason: str = "AFK"):
    afk_db[interaction.user.id] = {'reason': reason}
    await interaction.response.send_message(f"💤 You are now AFK: {reason}")

@bot.tree.command(name="poll", description="Create a quick poll")
@app_commands.describe(question="Question", option1="Option 1", option2="Option 2", option3="Option 3", option4="Option 4")
async def poll_slash(interaction: discord.Interaction, question: str, option1: str, option2: str, option3: str = None, option4: str = None):
    options = [option1, option2]
    if option3: options.append(option3)
    if option4: options.append(option4)
    emojis = ['1️⃣', '2️⃣', '3️⃣', '4️⃣']
    embed = discord.Embed(title=f"📊 {question}", description="\n".join(f"{emojis[i]} {opt}" for i, opt in enumerate(options)), color=0xff6b35)
    embed.set_footer(text=f"Poll by {interaction.user}")
    await interaction.response.send_message(embed=embed)
    msg = await interaction.original_response()
    for i in range(len(options)):
        await msg.add_reaction(emojis[i])

@bot.tree.command(name="giveaway", description="Start a giveaway")
@app_commands.describe(prize="Prize", minutes="Duration in minutes", winners="Number of winners")
@app_commands.checks.has_permissions(manage_guild=True)
async def giveaway_slash(interaction: discord.Interaction, prize: str, minutes: int, winners: int = 1):
    await interaction.response.defer()
    end_time = datetime.utcnow() + timedelta(minutes=minutes)
    gid = str(interaction.guild.id)
    if gid not in giveaways_db:
        giveaways_db[gid] = {}
    ga_id = str(int(datetime.utcnow().timestamp()))
    giveaways_db[gid][ga_id] = {
        'prize': prize, 'winners': winners, 'participants': [],
        'end_time': end_time.isoformat(), 'ended': False,
        'host': str(interaction.user.id)
    }
    save_json(GIVEAWAYS_FILE, giveaways_db)
    embed = discord.Embed(title=f"🎉 GIVEAWAY: {prize}", color=0xff6b35, timestamp=end_time)
    embed.add_field(name="Hosted by", value=interaction.user.mention, inline=True)
    embed.add_field(name="Entries", value="`0`", inline=True)
    embed.add_field(name="Winners", value=f"`{winners}`", inline=True)
    embed.set_footer(text="Ends at")
    view = GiveawayView(ga_id)
    msg = await interaction.followup.send(embed=embed, view=view)
    giveaways_db[gid][ga_id]['message_id'] = str(msg.id)
    giveaways_db[gid][ga_id]['channel_id'] = str(interaction.channel.id)
    save_json(GIVEAWAYS_FILE, giveaways_db)
    await asyncio.sleep(minutes * 60)
    await end_giveaway(interaction.guild, gid, ga_id)

@bot.tree.command(name="play", description="Play a song or Spotify link")
@app_commands.describe(query="Song name, YouTube URL or Spotify link")
async def play_slash(interaction: discord.Interaction, query: str):
    await interaction.response.defer()
    if not interaction.user.voice:
        await interaction.followup.send("❌ Join a voice channel first!")
        return
    vc = interaction.guild.voice_client
    if not vc:
        vc = await interaction.user.voice.channel.connect()
    await interaction.followup.send(f"🔍 Searching: `{query}`...")
    try:
        player = await get_source(query)
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {e}")
        return
    data = get_guild_data(interaction.guild.id)
    if vc.is_playing() or vc.is_paused():
        data['queue'].append(player)
        embed = discord.Embed(description=f"📋 Added: **{player.title}** • Position `#{len(data['queue'])}`", color=0xff6b35)
        await interaction.followup.send(embed=embed, delete_after=5)
    else:
        data['current'] = player
        data['dj'] = interaction.user.id
        vc.play(player, after=lambda e: asyncio.run_coroutine_threadsafe(play_next(interaction.guild, vc, interaction), bot.loop))
        await update_panel(interaction, interaction.guild, vc)

@bot.tree.command(name="skip", description="Skip current song")
async def skip_slash(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    data = get_guild_data(interaction.guild.id)
    if data.get('dj') and interaction.user.id != data['dj']:
        needed = max(1, len([m for m in vc.channel.members if not m.bot]) // 2) if vc else 1
        await interaction.response.send_message(f"🗳️ **Vote to skip!** (0/{needed} votes)", view=VoteView('skip', interaction.guild, vc, needed))
        return
    if vc and (vc.is_playing() or vc.is_paused()):
        vc.stop()
        await interaction.response.send_message("⏭️ Skipped!", delete_after=3)
    else:
        await interaction.response.send_message("❌ Nothing is playing!", delete_after=3)

@bot.tree.command(name="stop", description="Stop and leave")
async def stop_slash(interaction: discord.Interaction):
    data = get_guild_data(interaction.guild.id)
    vc = interaction.guild.voice_client
    if data.get('dj') and interaction.user.id != data['dj']:
        needed = max(1, len([m for m in vc.channel.members if not m.bot]) // 2) if vc else 1
        await interaction.response.send_message(f"🗳️ **Vote to stop!** (0/{needed} votes)", view=VoteView('stop', interaction.guild, vc, needed))
        return
    data['queue'].clear()
    data['current'] = None
    data['dj'] = None
    if vc: await vc.disconnect()
    await interaction.response.send_message("⏹️ Stopped!", delete_after=3)

@bot.tree.command(name="pause", description="Pause the music")
async def pause_slash(interaction: discord.Interaction):
    data = get_guild_data(interaction.guild.id)
    if data.get('dj') and interaction.user.id != data['dj']:
        await interaction.response.send_message("❌ Only the DJ can pause!", ephemeral=True)
        return
    vc = interaction.guild.voice_client
    if vc and vc.is_playing():
        vc.pause()
        await interaction.response.send_message("⏸️ Paused!", delete_after=3)
    else:
        await interaction.response.send_message("❌ Nothing is playing!", delete_after=3)

@bot.tree.command(name="resume", description="Resume the music")
async def resume_slash(interaction: discord.Interaction):
    data = get_guild_data(interaction.guild.id)
    if data.get('dj') and interaction.user.id != data['dj']:
        await interaction.response.send_message("❌ Only the DJ can resume!", ephemeral=True)
        return
    vc = interaction.guild.voice_client
    if vc and vc.is_paused():
        vc.resume()
        await interaction.response.send_message("▶️ Resumed!", delete_after=3)
    else:
        await interaction.response.send_message("❌ Not paused!", delete_after=3)

@bot.tree.command(name="queue", description="Show the queue")
async def queue_slash(interaction: discord.Interaction):
    data = get_guild_data(interaction.guild.id)
    q = data['queue']
    if not q:
        await interaction.response.send_message("📋 Queue is empty!")
        return
    embed = discord.Embed(title="📋 Queue", color=0xff6b35)
    for i, s in enumerate(q, 1):
        embed.add_field(name=f"{i}.", value=s.title, inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="loop", description="Toggle loop")
async def loop_slash(interaction: discord.Interaction):
    data = get_guild_data(interaction.guild.id)
    if data.get('dj') and interaction.user.id != data['dj']:
        await interaction.response.send_message("❌ Only the DJ!", ephemeral=True)
        return
    data['loop'] = not data['loop']
    await interaction.response.send_message(f"🔁 Loop {'✅ On' if data['loop'] else '❌ Off'}!", delete_after=3)

@bot.tree.command(name="volume", description="Set volume 0-100")
@app_commands.describe(vol="Volume 0-100")
async def volume_slash(interaction: discord.Interaction, vol: int):
    data = get_guild_data(interaction.guild.id)
    if data.get('dj') and interaction.user.id != data['dj']:
        await interaction.response.send_message("❌ Only the DJ!", ephemeral=True)
        return
    vc = interaction.guild.voice_client
    if not vc or not vc.source:
        await interaction.response.send_message("❌ Nothing playing!")
        return
    if 0 <= vol <= 100:
        vc.source.volume = vol / 100
        await interaction.response.send_message(f"🔊 Volume: **{vol}%**", delete_after=3)
    else:
        await interaction.response.send_message("❌ Enter 0-100!")

@bot.tree.command(name="nowplaying", description="Show now playing panel")
async def nowplaying_slash(interaction: discord.Interaction):
    await interaction.response.defer()
    data = get_guild_data(interaction.guild.id)
    if data.get('current'):
        await update_panel(interaction, interaction.guild, interaction.guild.voice_client)
    else:
        await interaction.followup.send("❌ Nothing is playing!")

@bot.tree.command(name="join", description="Join your voice channel")
async def join_slash(interaction: discord.Interaction):
    if not interaction.user.voice:
        await interaction.response.send_message("❌ You are not in a voice channel!")
        return
    await interaction.user.voice.channel.connect()
    await interaction.response.send_message("✅ Joined!", delete_after=3)

@bot.tree.command(name="lyrics", description="Get lyrics")
@app_commands.describe(song="Song name (empty = current song)")
async def lyrics_slash(interaction: discord.Interaction, song: str = None):
    await interaction.response.defer()
    if not song:
        data = get_guild_data(interaction.guild.id)
        cur = data.get('current')
        if not cur:
            await interaction.followup.send("❌ Nothing is playing!")
            return
        song = cur.title
    result = await asyncio.get_event_loop().run_in_executor(None, lambda: get_lyrics(song))
    if not result:
        await interaction.followup.send(f"❌ Lyrics not found for: **{song}**")
        return
    if len(result) > 4000:
        result = result[:4000] + "\n..."
    embed = discord.Embed(title=f"🎵 Lyrics: {song}", description=result, color=0xff6b35)
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="kick", description="Kick a member")
@app_commands.describe(member="Member", reason="Reason")
async def kick_slash(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    if not is_owner(interaction.user.id) and not interaction.user.guild_permissions.kick_members:
        await interaction.response.send_message("❌ You don't have permission!", ephemeral=True)
        return
    if not can_act_on(interaction.user, member, interaction.guild):
        await interaction.response.send_message("❌ You can't kick this member!", ephemeral=True)
        return
    try:
        await member.kick(reason=f"{reason} | By {interaction.user}")
        case_id = log_case(interaction.guild.id, 'kick', member, interaction.user, reason)
        await post_case_log(interaction.guild, case_id, 'kick', member, interaction.user, reason)
        embed = discord.Embed(description=f"👢 **{member}** was kicked.\nReason: {reason}", color=0xff6b35)
        embed.set_footer(text=f"Case #{case_id}")
        await interaction.response.send_message(embed=embed)
    except discord.Forbidden:
        await interaction.response.send_message("❌ I don't have permission!", ephemeral=True)

@bot.tree.command(name="ban", description="Ban a member")
@app_commands.describe(member="Member", reason="Reason", delete_days="Days 0-7")
async def ban_slash(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided", delete_days: int = 0):
    if not is_owner(interaction.user.id) and not interaction.user.guild_permissions.ban_members:
        await interaction.response.send_message("❌ You don't have permission!", ephemeral=True)
        return
    if not can_act_on(interaction.user, member, interaction.guild):
        await interaction.response.send_message("❌ You can't ban this member!", ephemeral=True)
        return
    try:
        await member.ban(reason=f"{reason} | By {interaction.user}", delete_message_seconds=max(0, min(7, delete_days)) * 86400)
        case_id = log_case(interaction.guild.id, 'ban', member, interaction.user, reason)
        await post_case_log(interaction.guild, case_id, 'ban', member, interaction.user, reason)
        embed = discord.Embed(description=f"🔨 **{member}** was banned.\nReason: {reason}", color=0xff0000)
        embed.set_footer(text=f"Case #{case_id}")
        await interaction.response.send_message(embed=embed)
    except discord.Forbidden:
        await interaction.response.send_message("❌ I don't have permission!", ephemeral=True)

@bot.tree.command(name="unban", description="Unban a user by ID")
@app_commands.describe(user_id="User ID", reason="Reason")
async def unban_slash(interaction: discord.Interaction, user_id: str, reason: str = "No reason provided"):
    if not is_owner(interaction.user.id) and not interaction.user.guild_permissions.ban_members:
        await interaction.response.send_message("❌ You don't have permission!", ephemeral=True)
        return
    try:
        user = await bot.fetch_user(int(user_id))
        await interaction.guild.unban(user, reason=f"{reason} | By {interaction.user}")
        case_id = log_case(interaction.guild.id, 'unban', user, interaction.user, reason)
        await post_case_log(interaction.guild, case_id, 'unban', user, interaction.user, reason)
        embed = discord.Embed(description=f"✅ **{user}** was unbanned.", color=0x00ff00)
        embed.set_footer(text=f"Case #{case_id}")
        await interaction.response.send_message(embed=embed)
    except:
        await interaction.response.send_message("❌ User not found or not banned!", ephemeral=True)

@bot.tree.command(name="timeout", description="Timeout a member")
@app_commands.describe(member="Member", minutes="Minutes", reason="Reason")
async def timeout_slash(interaction: discord.Interaction, member: discord.Member, minutes: int, reason: str = "No reason provided"):
    if not is_owner(interaction.user.id) and not interaction.user.guild_permissions.moderate_members:
        await interaction.response.send_message("❌ You don't have permission!", ephemeral=True)
        return
    if not can_act_on(interaction.user, member, interaction.guild):
        await interaction.response.send_message("❌ You can't timeout this member!", ephemeral=True)
        return
    try:
        await member.timeout(timedelta(minutes=minutes), reason=f"{reason} | By {interaction.user}")
        case_id = log_case(interaction.guild.id, 'timeout', member, interaction.user, reason, duration=minutes)
        await post_case_log(interaction.guild, case_id, 'timeout', member, interaction.user, reason, duration=minutes)
        embed = discord.Embed(description=f"🔇 **{member}** timed out for {minutes} min.\nReason: {reason}", color=0xff6b35)
        embed.set_footer(text=f"Case #{case_id}")
        await interaction.response.send_message(embed=embed)
    except discord.Forbidden:
        await interaction.response.send_message("❌ I don't have permission!", ephemeral=True)

@bot.tree.command(name="untimeout", description="Remove timeout")
@app_commands.describe(member="Member", reason="Reason")
async def untimeout_slash(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    if not is_owner(interaction.user.id) and not interaction.user.guild_permissions.moderate_members:
        await interaction.response.send_message("❌ You don't have permission!", ephemeral=True)
        return
    try:
        await member.timeout(None, reason=f"{reason} | By {interaction.user}")
        case_id = log_case(interaction.guild.id, 'untimeout', member, interaction.user, reason)
        await post_case_log(interaction.guild, case_id, 'untimeout', member, interaction.user, reason)
        embed = discord.Embed(description=f"🔊 Timeout removed from **{member}**.", color=0x00ff00)
        embed.set_footer(text=f"Case #{case_id}")
        await interaction.response.send_message(embed=embed)
    except discord.Forbidden:
        await interaction.response.send_message("❌ I don't have permission!", ephemeral=True)

@bot.tree.command(name="mute", description="Mute a member")
@app_commands.describe(member="Member", reason="Reason")
async def mute_slash(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    if not is_owner(interaction.user.id) and not interaction.user.guild_permissions.manage_roles:
        await interaction.response.send_message("❌ You don't have permission!", ephemeral=True)
        return
    if not can_act_on(interaction.user, member, interaction.guild):
        await interaction.response.send_message("❌ You can't mute this member!", ephemeral=True)
        return
    await interaction.response.defer()
    role = await get_muted_role(interaction.guild)
    if role in member.roles:
        await interaction.followup.send(f"❌ **{member}** is already muted!")
        return
    try:
        await member.add_roles(role, reason=f"{reason} | By {interaction.user}")
        case_id = log_case(interaction.guild.id, 'mute', member, interaction.user, reason)
        await post_case_log(interaction.guild, case_id, 'mute', member, interaction.user, reason)
        embed = discord.Embed(description=f"🔇 **{member}** was muted.\nReason: {reason}", color=0xff6b35)
        embed.set_footer(text=f"Case #{case_id}")
        await interaction.followup.send(embed=embed)
    except discord.Forbidden:
        await interaction.followup.send("❌ I don't have permission!")

@bot.tree.command(name="unmute", description="Unmute a member")
@app_commands.describe(member="Member", reason="Reason")
async def unmute_slash(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    if not is_owner(interaction.user.id) and not interaction.user.guild_permissions.manage_roles:
        await interaction.response.send_message("❌ You don't have permission!", ephemeral=True)
        return
    role = discord.utils.get(interaction.guild.roles, name="Muted")
    if role is None or role not in member.roles:
        await interaction.response.send_message(f"❌ **{member}** is not muted!", ephemeral=True)
        return
    try:
        await member.remove_roles(role)
        case_id = log_case(interaction.guild.id, 'unmute', member, interaction.user, reason)
        await post_case_log(interaction.guild, case_id, 'unmute', member, interaction.user, reason)
        embed = discord.Embed(description=f"🔊 **{member}** was unmuted.", color=0x00ff00)
        embed.set_footer(text=f"Case #{case_id}")
        await interaction.response.send_message(embed=embed)
    except discord.Forbidden:
        await interaction.response.send_message("❌ I don't have permission!", ephemeral=True)

@bot.tree.command(name="softban", description="Softban a member")
@app_commands.describe(member="Member", reason="Reason", delete_days="Days 1-7")
async def softban_slash(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided", delete_days: int = 1):
    if not is_owner(interaction.user.id) and not interaction.user.guild_permissions.ban_members:
        await interaction.response.send_message("❌ You don't have permission!", ephemeral=True)
        return
    if not can_act_on(interaction.user, member, interaction.guild):
        await interaction.response.send_message("❌ You can't softban this member!", ephemeral=True)
        return
    try:
        await member.ban(reason=f"Softban: {reason}", delete_message_seconds=max(1, min(7, delete_days)) * 86400)
        await interaction.guild.unban(member)
        case_id = log_case(interaction.guild.id, 'softban', member, interaction.user, reason)
        await post_case_log(interaction.guild, case_id, 'softban', member, interaction.user, reason)
        embed = discord.Embed(description=f"🔨 **{member}** was softbanned.\nReason: {reason}", color=0xff6b35)
        embed.set_footer(text=f"Case #{case_id}")
        await interaction.response.send_message(embed=embed)
    except discord.Forbidden:
        await interaction.response.send_message("❌ I don't have permission!", ephemeral=True)

@bot.tree.command(name="purge", description="Delete multiple messages")
@app_commands.describe(amount="1-100")
async def purge_slash(interaction: discord.Interaction, amount: int):
    if not is_owner(interaction.user.id) and not interaction.user.guild_permissions.manage_messages:
        await interaction.response.send_message("❌ You don't have permission!", ephemeral=True)
        return
    if amount < 1 or amount > 100:
        await interaction.response.send_message("❌ Enter 1-100!", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    deleted = await interaction.channel.purge(limit=amount)
    await interaction.followup.send(f"🗑️ Deleted **{len(deleted)}** messages!", ephemeral=True)
    log_embed = discord.Embed(description=f"🗑️ **{len(deleted)} messages** purged in {interaction.channel.mention}\nBy: {interaction.user}", color=0xff6b35, timestamp=datetime.utcnow())
    await send_log(interaction.guild, log_embed)

@bot.tree.command(name="history", description="View a member's moderation history")
@app_commands.describe(member="Member")
async def history_slash(interaction: discord.Interaction, member: discord.Member):
    if not is_owner(interaction.user.id) and not interaction.user.guild_permissions.kick_members:
        await interaction.response.send_message("❌ You don't have permission!", ephemeral=True)
        return
    cases = get_user_cases(interaction.guild.id, member.id)
    if not cases:
        await interaction.response.send_message(f"📋 **{member}** has no history!")
        return
    embed = discord.Embed(title=f"📋 History: {member}", color=0xff6b35)
    embed.set_thumbnail(url=member.display_avatar.url)
    for c in cases[-15:][::-1]:
        emoji = ACTION_EMOJIS.get(c['action'], '📌')
        dur = f" ({c['duration']} min)" if c.get('duration') else ""
        embed.add_field(
            name=f"{emoji} Case #{c['case_id']} — {c['action'].title()}{dur}",
            value=f"By: {c['moderator_tag']}\nReason: {c['reason']}\nDate: {c['timestamp'][:10]}",
            inline=False
        )
    embed.set_footer(text=f"Total: {len(cases)} (last 15)")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="case", description="Look up a specific case")
@app_commands.describe(case_id="Case number")
async def case_slash(interaction: discord.Interaction, case_id: int):
    if not is_owner(interaction.user.id) and not interaction.user.guild_permissions.kick_members:
        await interaction.response.send_message("❌ You don't have permission!", ephemeral=True)
        return
    c = get_case_by_id(interaction.guild.id, case_id)
    if not c:
        await interaction.response.send_message(f"❌ Case #{case_id} not found!", ephemeral=True)
        return
    emoji = ACTION_EMOJIS.get(c['action'], '📌')
    dur = f" ({c['duration']} min)" if c.get('duration') else ""
    embed = discord.Embed(title=f"{emoji} Case #{c['case_id']} — {c['action'].title()}{dur}", color=0xff6b35)
    embed.add_field(name="Target", value=c['target_tag'], inline=True)
    embed.add_field(name="Moderator", value=c['moderator_tag'], inline=True)
    embed.add_field(name="Reason", value=c['reason'], inline=False)
    embed.add_field(name="Date", value=c['timestamp'][:19].replace('T', ' '), inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="balance", description="Check your balance")
@app_commands.describe(member="Member to check")
async def balance_slash(interaction: discord.Interaction, member: discord.Member = None):
    member = member or interaction.user
    econ = get_econ(interaction.guild.id, member.id)
    embed = discord.Embed(title=f"💰 {member.display_name}'s Balance", color=0xff6b35)
    embed.add_field(name="👛 Wallet", value=f"${econ['wallet']:,}", inline=True)
    embed.add_field(name="🏦 Bank", value=f"${econ['bank']:,}", inline=True)
    embed.add_field(name="💎 Total", value=f"${econ['wallet'] + econ['bank']:,}", inline=True)
    embed.set_thumbnail(url=member.display_avatar.url)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="daily", description="Claim your daily reward")
async def daily_slash(interaction: discord.Interaction):
    econ = get_econ(interaction.guild.id, interaction.user.id)
    now = datetime.utcnow()
    if econ['last_daily']:
        last = datetime.fromisoformat(econ['last_daily'])
        diff = (now - last).total_seconds()
        if diff < 86400:
            remaining = 86400 - diff
            h, m = divmod(int(remaining), 3600)
            m //= 60
            await interaction.response.send_message(f"⏰ Daily already claimed! Come back in **{h}h {m}m**!")
            return
    reward = random.randint(200, 500)
    econ['wallet'] += reward
    econ['last_daily'] = now.isoformat()
    save_econ()
    embed = discord.Embed(description=f"💰 You claimed **${reward:,}** daily reward!\n💛 Balance: **${econ['wallet']:,}**", color=0xffd700)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="work", description="Work to earn money")
async def work_slash(interaction: discord.Interaction):
    econ = get_econ(interaction.guild.id, interaction.user.id)
    now = datetime.utcnow()
    if econ['last_work']:
        last = datetime.fromisoformat(econ['last_work'])
        diff = (now - last).total_seconds()
        if diff < 3600:
            remaining = 3600 - diff
            m = int(remaining // 60)
            await interaction.response.send_message(f"⏰ You're tired! Rest for **{m} minutes**!")
            return
    jobs = ["programmer", "chef", "driver", "teacher", "doctor", "musician"]
    job = random.choice(jobs)
    reward = random.randint(50, 200)
    econ['wallet'] += reward
    econ['last_work'] = now.isoformat()
    save_econ()
    embed = discord.Embed(description=f"💼 You worked as a **{job}** and earned **${reward:,}**!\n💛 Balance: **${econ['wallet']:,}**", color=0x00ff66)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="deposit", description="Deposit money to bank")
@app_commands.describe(amount="Amount or 'all'")
async def deposit_slash(interaction: discord.Interaction, amount: str):
    econ = get_econ(interaction.guild.id, interaction.user.id)
    if amount.lower() == 'all':
        amt = econ['wallet']
    else:
        try:
            amt = int(amount)
        except:
            await interaction.response.send_message("❌ Enter a valid amount or 'all'!", ephemeral=True)
            return
    if amt <= 0 or amt > econ['wallet']:
        await interaction.response.send_message(f"❌ You only have **${econ['wallet']:,}** in wallet!", ephemeral=True)
        return
    econ['wallet'] -= amt
    econ['bank'] += amt
    save_econ()
    embed = discord.Embed(description=f"🏦 Deposited **${amt:,}** to bank!\n👛 Wallet: **${econ['wallet']:,}** | 🏦 Bank: **${econ['bank']:,}**", color=0x00ff66)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="withdraw", description="Withdraw money from bank")
@app_commands.describe(amount="Amount or 'all'")
async def withdraw_slash(interaction: discord.Interaction, amount: str):
    econ = get_econ(interaction.guild.id, interaction.user.id)
    if amount.lower() == 'all':
        amt = econ['bank']
    else:
        try:
            amt = int(amount)
        except:
            await interaction.response.send_message("❌ Enter a valid amount or 'all'!", ephemeral=True)
            return
    if amt <= 0 or amt > econ['bank']:
        await interaction.response.send_message(f"❌ You only have **${econ['bank']:,}** in bank!", ephemeral=True)
        return
    econ['bank'] -= amt
    econ['wallet'] += amt
    save_econ()
    embed = discord.Embed(description=f"👛 Withdrew **${amt:,}** from bank!\n👛 Wallet: **${econ['wallet']:,}** | 🏦 Bank: **${econ['bank']:,}**", color=0x00ff66)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="rob", description="Rob another member's wallet")
@app_commands.describe(member="Member to rob")
async def rob_slash(interaction: discord.Interaction, member: discord.Member):
    if member.id == interaction.user.id or member.bot:
        await interaction.response.send_message("❌ Invalid target!", ephemeral=True)
        return
    robber = get_econ(interaction.guild.id, interaction.user.id)
    victim = get_econ(interaction.guild.id, member.id)
    if victim['wallet'] < 100:
        await interaction.response.send_message(f"❌ **{member.display_name}** doesn't have enough money!", ephemeral=True)
        return
    if robber['wallet'] < 200:
        await interaction.response.send_message("❌ You need at least **$200** to rob!", ephemeral=True)
        return
    if random.random() < 0.4:
        fine = random.randint(100, 300)
        robber['wallet'] = max(0, robber['wallet'] - fine)
        save_econ()
        embed = discord.Embed(description=f"🚔 Got caught! Paid **${fine:,}** fine!\n💰 Balance: **${robber['wallet']:,}**", color=0xff3333)
    else:
        stolen = random.randint(int(victim['wallet'] * 0.1), int(victim['wallet'] * 0.4))
        victim['wallet'] -= stolen
        robber['wallet'] += stolen
        save_econ()
        embed = discord.Embed(description=f"💰 Robbed **${stolen:,}** from **{member.display_name}**!\n💰 Balance: **${robber['wallet']:,}**", color=0x00ff66)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="pay", description="Pay money to another member")
@app_commands.describe(member="Member to pay", amount="Amount to pay")
async def pay_slash(interaction: discord.Interaction, member: discord.Member, amount: int):
    if member.id == interaction.user.id or amount <= 0:
        await interaction.response.send_message("❌ Invalid!", ephemeral=True)
        return
    payer = get_econ(interaction.guild.id, interaction.user.id)
    receiver = get_econ(interaction.guild.id, member.id)
    if payer['wallet'] < amount:
        await interaction.response.send_message(f"❌ You only have **${payer['wallet']:,}**!", ephemeral=True)
        return
    payer['wallet'] -= amount
    receiver['wallet'] += amount
    save_econ()
    embed = discord.Embed(description=f"💸 You paid **${amount:,}** to {member.mention}!", color=0x00ff66)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="economy-leaderboard", description="Show richest members")
async def econ_lb_slash(interaction: discord.Interaction):
    gid = str(interaction.guild.id)
    if gid not in economy_db or not economy_db[gid]:
        await interaction.response.send_message("❌ No data yet!")
        return
    sorted_users = sorted(economy_db[gid].items(), key=lambda x: x[1]['wallet'] + x[1]['bank'], reverse=True)[:10]
    embed = discord.Embed(title="💰 Economy Leaderboard", color=0xffd700)
    medals = ['🥇', '🥈', '🥉']
    for i, (uid, data) in enumerate(sorted_users, 1):
        member = interaction.guild.get_member(int(uid))
        name = member.display_name if member else f"User {uid}"
        medal = medals[i-1] if i <= 3 else f"`{i}.`"
        total = data['wallet'] + data['bank']
        embed.add_field(name=f"{medal} {name}", value=f"💎 **${total:,}** | 👛 ${data['wallet']:,} | 🏦 ${data['bank']:,}", inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="blackjack", description="Play blackjack")
@app_commands.describe(bet="Amount to bet")
async def blackjack_slash(interaction: discord.Interaction, bet: int):
    econ = get_econ(interaction.guild.id, interaction.user.id)
    if bet <= 0 or bet > econ['wallet']:
        await interaction.response.send_message(f"❌ Invalid bet! You have **${econ['wallet']:,}**!", ephemeral=True)
        return
    key = f"{interaction.guild.id}_{interaction.user.id}"
    if key in active_bj:
        await interaction.response.send_message("❌ You already have an active game!", ephemeral=True)
        return
    econ['wallet'] -= bet
    save_econ()
    deck = make_deck()
    player = [deck.pop(), deck.pop()]
    dealer = [deck.pop(), deck.pop()]
    active_bj[key] = {'player': player, 'dealer': dealer, 'deck': deck}
    pval = hand_value(player)
    embed = discord.Embed(title="🃏 Blackjack", color=0xff6b35)
    embed.add_field(name=f"{interaction.user.display_name}'s Hand", value=f"{hand_str(player)}\nValue: {'Soft ' if is_soft(player) else ''}{pval}", inline=False)
    embed.add_field(name="Dealer Hand", value=f"{hand_str(dealer, hide_second=True)}\nValue: {hand_value([dealer[0]])}", inline=False)
    embed.add_field(name="Cards Remaining", value=f"`{len(deck)}` remaining", inline=False)
    embed.set_footer(text=f"Bet: ${bet:,} | Balance: ${econ['wallet']:,}")
    if pval == 21:
        winnings = int(bet * 2.5)
        econ['wallet'] += winnings
        save_econ()
        del active_bj[key]
        embed.add_field(name="🎉 BLACKJACK!", value=f"You win **${winnings:,}**!", inline=False)
        await interaction.response.send_message(embed=embed)
        return
    view = BlackjackView(interaction.guild.id, interaction.user.id, bet)
    await interaction.response.send_message(embed=embed, view=view)

@bot.tree.command(name="slots", description="Play slots")
@app_commands.describe(bet="Amount to bet")
async def slots_slash(interaction: discord.Interaction, bet: int):
    econ = get_econ(interaction.guild.id, interaction.user.id)
    if bet <= 0 or bet > econ['wallet']:
        await interaction.response.send_message(f"❌ Invalid bet! You have **${econ['wallet']:,}**!", ephemeral=True)
        return
    econ['wallet'] -= bet
    symbols = ['🍒', '🍋', '🍊', '🍇', '⭐', '💎', '7️⃣']
    weights = [30, 25, 20, 15, 5, 3, 2]
    reels = random.choices(symbols, weights=weights, k=3)
    embed = discord.Embed(title="🎰 Slots", color=0xff6b35)
    embed.add_field(name="Result", value=f"[ {reels[0]} | {reels[1]} | {reels[2]} ]", inline=False)
    if reels[0] == reels[1] == reels[2]:
        multipliers = {'7️⃣': 50, '💎': 20, '⭐': 10, '🍇': 5, '🍊': 4, '🍋': 3, '🍒': 2}
        mult = multipliers.get(reels[0], 2)
        winnings = bet * mult
        econ['wallet'] += winnings
        embed.add_field(name="🎉 JACKPOT!", value=f"**{reels[0]} x3** — Win **${winnings:,}**! (x{mult})", inline=False)
        embed.color = 0xffd700
    elif reels[0] == reels[1] or reels[1] == reels[2] or reels[0] == reels[2]:
        winnings = int(bet * 1.5)
        econ['wallet'] += winnings
        embed.add_field(name="✅ Two of a kind!", value=f"Win **${winnings:,}**!", inline=False)
        embed.color = 0x00ff66
    else:
        embed.add_field(name="😢 No match!", value=f"Lost **${bet:,}**!", inline=False)
        embed.color = 0xff3333
    save_econ()
    embed.set_footer(text=f"Balance: ${econ['wallet']:,}")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="coinflip", description="Flip a coin")
@app_commands.describe(bet="Amount to bet", choice="heads or tails")
@app_commands.choices(choice=[app_commands.Choice(name="Heads", value="heads"), app_commands.Choice(name="Tails", value="tails")])
async def coinflip_slash(interaction: discord.Interaction, bet: int, choice: str):
    econ = get_econ(interaction.guild.id, interaction.user.id)
    if bet <= 0 or bet > econ['wallet']:
        await interaction.response.send_message(f"❌ Invalid bet! You have **${econ['wallet']:,}**!", ephemeral=True)
        return
    econ['wallet'] -= bet
    result = random.choice(['heads', 'tails'])
    if result == choice:
        econ['wallet'] += bet * 2
        embed = discord.Embed(description=f"🪙 **{result.title()}**!\n🎉 You won **${bet*2:,}**!\n💰 Balance: **${econ['wallet']:,}**", color=0x00ff66)
    else:
        embed = discord.Embed(description=f"🪙 **{result.title()}**!\n😢 You lost **${bet:,}**!\n💰 Balance: **${econ['wallet']:,}**", color=0xff3333)
    save_econ()
    await interaction.response.send_message(embed=embed)

# ========== PLAYLIST GROUP ==========
playlist_group = app_commands.Group(name="playlist", description="Playlist commands")

@playlist_group.command(name="create", description="Create a new playlist")
@app_commands.describe(name="Playlist name")
async def playlist_create(interaction: discord.Interaction, name: str):
    gid = str(interaction.guild.id)
    if gid not in playlists_db:
        playlists_db[gid] = {}
    if name in playlists_db[gid]:
        await interaction.response.send_message(f"❌ Playlist **{name}** already exists!", ephemeral=True)
        return
    playlists_db[gid][name] = {'owner': interaction.user.id, 'songs': []}
    save_json(PLAYLISTS_FILE, playlists_db)
    await interaction.response.send_message(f"✅ Playlist **{name}** created!")

@playlist_group.command(name="add", description="Add a song to a playlist")
@app_commands.describe(name="Playlist name", song="Song")
async def playlist_add(interaction: discord.Interaction, name: str, song: str):
    gid = str(interaction.guild.id)
    if gid not in playlists_db or name not in playlists_db[gid]:
        await interaction.response.send_message(f"❌ Playlist **{name}** not found!", ephemeral=True)
        return
    pl = playlists_db[gid][name]
    if pl['owner'] != interaction.user.id:
        await interaction.response.send_message("❌ You are not the owner!", ephemeral=True)
        return
    pl['songs'].append(song)
    save_json(PLAYLISTS_FILE, playlists_db)
    await interaction.response.send_message(f"✅ Added **{song}** to **{name}**!")

@playlist_group.command(name="removesong", description="Remove a song from playlist")
@app_commands.describe(name="Playlist name", index="Song number")
async def playlist_removesong(interaction: discord.Interaction, name: str, index: int):
    gid = str(interaction.guild.id)
    if gid not in playlists_db or name not in playlists_db[gid]:
        await interaction.response.send_message(f"❌ Playlist **{name}** not found!", ephemeral=True)
        return
    pl = playlists_db[gid][name]
    if pl['owner'] != interaction.user.id:
        await interaction.response.send_message("❌ You are not the owner!", ephemeral=True)
        return
    if index < 1 or index > len(pl['songs']):
        await interaction.response.send_message("❌ Invalid number!", ephemeral=True)
        return
    removed = pl['songs'].pop(index - 1)
    save_json(PLAYLISTS_FILE, playlists_db)
    await interaction.response.send_message(f"🗑️ Removed **{removed}** from **{name}**!")

@playlist_group.command(name="remove", description="Delete a playlist")
@app_commands.describe(name="Playlist name")
async def playlist_remove(interaction: discord.Interaction, name: str):
    gid = str(interaction.guild.id)
    if gid not in playlists_db or name not in playlists_db[gid]:
        await interaction.response.send_message(f"❌ Playlist **{name}** not found!", ephemeral=True)
        return
    if playlists_db[gid][name]['owner'] != interaction.user.id:
        await interaction.response.send_message("❌ You are not the owner!", ephemeral=True)
        return
    del playlists_db[gid][name]
    save_json(PLAYLISTS_FILE, playlists_db)
    await interaction.response.send_message(f"🗑️ Playlist **{name}** deleted!")

@playlist_group.command(name="list", description="Show all playlists")
async def playlist_list(interaction: discord.Interaction):
    gid = str(interaction.guild.id)
    if gid not in playlists_db or not playlists_db[gid]:
        await interaction.response.send_message("📋 No playlists found!")
        return
    embed = discord.Embed(title="📋 Playlists", color=0xff6b35)
    for pl_name, pl_data in playlists_db[gid].items():
        embed.add_field(name=pl_name, value=f"Owner: <@{pl_data['owner']}> | Songs: `{len(pl_data['songs'])}`", inline=False)
    await interaction.response.send_message(embed=embed)

@playlist_group.command(name="view", description="View songs in a playlist")
@app_commands.describe(name="Playlist name")
async def playlist_view(interaction: discord.Interaction, name: str):
    gid = str(interaction.guild.id)
    if gid not in playlists_db or name not in playlists_db[gid]:
        await interaction.response.send_message(f"❌ Playlist **{name}** not found!", ephemeral=True)
        return
    pl = playlists_db[gid][name]
    if not pl['songs']:
        await interaction.response.send_message(f"📋 Playlist **{name}** is empty!")
        return
    embed = discord.Embed(title=f"📋 {name}", color=0xff6b35)
    for i, song in enumerate(pl['songs'], 1):
        embed.add_field(name=f"{i}.", value=song, inline=False)
    await interaction.response.send_message(embed=embed)

@playlist_group.command(name="play", description="Play a playlist")
@app_commands.describe(name="Playlist name")
async def playlist_play(interaction: discord.Interaction, name: str):
    await interaction.response.defer()
    gid = str(interaction.guild.id)
    if gid not in playlists_db or name not in playlists_db[gid]:
        await interaction.followup.send(f"❌ Playlist **{name}** not found!")
        return
    if not interaction.user.voice:
        await interaction.followup.send("❌ Join a voice channel first!")
        return
    pl = playlists_db[gid][name]
    if not pl['songs']:
        await interaction.followup.send(f"❌ Playlist **{name}** is empty!")
        return
    vc = interaction.guild.voice_client
    if not vc:
        vc = await interaction.user.voice.channel.connect()
    data = get_guild_data(interaction.guild.id)
    data['dj'] = interaction.user.id
    await interaction.followup.send(f"🎵 Loading **{name}** ({len(pl['songs'])} songs)...")
    first = True
    for song in pl['songs']:
        try:
            player = await get_source(song)
            if first and not vc.is_playing():
                data['current'] = player
                vc.play(player, after=lambda e: asyncio.run_coroutine_threadsafe(play_next(interaction.guild, vc, interaction), bot.loop))
                await update_panel(interaction, interaction.guild, vc)
                first = False
            else:
                data['queue'].append(player)
        except:
            pass

# ========== HELP ==========
@bot.tree.command(name="help", description="Show all commands")
async def help_slash(interaction: discord.Interaction):
    embed = discord.Embed(title="📖 Bot Commands (.prefix & /slash)", color=0xff6b35)
    embed.add_field(name="🎵 Music", value="`play` `skip` `stop` `pause` `resume` `queue` `loop` `volume` `np` `lyrics` `join`", inline=False)
    embed.add_field(name="📋 Playlists", value="`/playlist create/add/removesong/remove/play/list/view`", inline=False)
    embed.add_field(name="🛡️ Moderation", value="`kick` `ban` `unban` `timeout` `untimeout` `mute` `unmute` `softban` `purge` `history` `case`", inline=False)
    embed.add_field(name="📊 Leveling", value="`.rank` `.lb` / `/rank` `/leaderboard`", inline=False)
    embed.add_field(name="🎉 Giveaway", value="`.giveaway <min> <winners> <prize>` / `/giveaway`", inline=False)
    embed.add_field(name="🎫 Ticket", value="Ticket kanalındakı **Create Ticket** düyməsi", inline=False)
    embed.add_field(name="💰 Economy", value="`balance` `daily` `work` `deposit` `withdraw` `rob` `pay` `economy-leaderboard`", inline=False)
    embed.add_field(name="🎰 Casino", value="`blackjack` `slots` `coinflip`", inline=False)
    embed.add_field(name="🎮 Community", value="`poll` `afk`", inline=False)
    embed.add_field(name="💡 Utility", value="`ping`", inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        msg = "❌ You don't have permission!"
    elif isinstance(error, app_commands.CommandInvokeError):
        msg = f"❌ Error: {error.original}"
    else:
        msg = f"❌ Error: {error}"
    try:
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
    except:
        pass

# ========== PREFIX COMMANDS ==========
@bot.command(name="ping")
async def ping_p(ctx):
    embed = discord.Embed(title="🏓 Pong!", color=0xff6b35)
    embed.add_field(name="Latency", value=f"`{round(bot.latency * 1000)}ms`")
    await ctx.send(embed=embed)

@bot.command(name="rank")
async def rank_p(ctx, member: discord.Member = None):
    member = member or ctx.author
    udata = get_user_data(ctx.guild.id, member.id)
    xp = udata['xp']
    level = get_level(xp)
    embed = discord.Embed(title=f"📊 {member.display_name}'s Rank", color=0xff6b35)
    embed.add_field(name="Level", value=f"`{level}`", inline=True)
    embed.add_field(name="XP", value=f"`{xp}/{xp_for_level(level+1)}`", inline=True)
    embed.set_thumbnail(url=member.display_avatar.url)
    await ctx.send(embed=embed)

@bot.command(name="leaderboard", aliases=["lb"])
async def leaderboard_p(ctx):
    gid = str(ctx.guild.id)
    if gid not in levels_db or not levels_db[gid]:
        await ctx.send("❌ No data yet!")
        return
    sorted_users = sorted(levels_db[gid].items(), key=lambda x: x[1]['xp'], reverse=True)[:10]
    embed = discord.Embed(title="🏆 XP Leaderboard", color=0xff6b35)
    for i, (uid, data) in enumerate(sorted_users, 1):
        member = ctx.guild.get_member(int(uid))
        name = member.display_name if member else f"User {uid}"
        embed.add_field(name=f"{i}. {name}", value=f"Level `{get_level(data['xp'])}` • XP `{data['xp']}`", inline=False)
    await ctx.send(embed=embed)

@bot.command(name="afk")
async def afk_p(ctx, *, reason: str = "AFK"):
    afk_db[ctx.author.id] = {'reason': reason}
    await ctx.send(f"💤 You are now AFK: {reason}")

@bot.command(name="poll")
async def poll_p(ctx, question: str, option1: str, option2: str, option3: str = None, option4: str = None):
    options = [option1, option2]
    if option3: options.append(option3)
    if option4: options.append(option4)
    emojis = ['1️⃣', '2️⃣', '3️⃣', '4️⃣']
    embed = discord.Embed(title=f"📊 {question}", description="\n".join(f"{emojis[i]} {opt}" for i, opt in enumerate(options)), color=0xff6b35)
    embed.set_footer(text=f"Poll by {ctx.author}")
    msg = await ctx.send(embed=embed)
    for i in range(len(options)):
        await msg.add_reaction(emojis[i])

@bot.command(name="giveaway")
@commands.has_permissions(manage_guild=True)
async def giveaway_p(ctx, minutes: int, winners: int = 1, *, prize: str):
    end_time = datetime.utcnow() + timedelta(minutes=minutes)
    gid = str(ctx.guild.id)
    if gid not in giveaways_db:
        giveaways_db[gid] = {}
    ga_id = str(int(datetime.utcnow().timestamp()))
    giveaways_db[gid][ga_id] = {
        'prize': prize, 'winners': winners, 'participants': [],
        'end_time': end_time.isoformat(), 'ended': False,
        'host': str(ctx.author.id)
    }
    save_json(GIVEAWAYS_FILE, giveaways_db)
    embed = discord.Embed(title=f"🎉 GIVEAWAY: {prize}", color=0xff6b35, timestamp=end_time)
    embed.add_field(name="Hosted by", value=ctx.author.mention, inline=True)
    embed.add_field(name="Entries", value="`0`", inline=True)
    embed.add_field(name="Winners", value=f"`{winners}`", inline=True)
    embed.set_footer(text="Ends at")
    msg = await ctx.send(embed=embed, view=GiveawayView(ga_id))
    giveaways_db[gid][ga_id]['message_id'] = str(msg.id)
    giveaways_db[gid][ga_id]['channel_id'] = str(ctx.channel.id)
    save_json(GIVEAWAYS_FILE, giveaways_db)
    await asyncio.sleep(minutes * 60)
    await end_giveaway(ctx.guild, gid, ga_id)

@bot.command(name="kick")
@commands.has_permissions(kick_members=True)
async def kick_p(ctx, member: discord.Member, *, reason: str = "No reason provided"):
    if not can_act_on(ctx.author, member, ctx.guild):
        await ctx.send("❌ You can't kick this member!")
        return
    try:
        await member.kick(reason=f"{reason} | By {ctx.author}")
        case_id = log_case(ctx.guild.id, 'kick', member, ctx.author, reason)
        await post_case_log(ctx.guild, case_id, 'kick', member, ctx.author, reason)
        embed = discord.Embed(description=f"👢 **{member}** was kicked.\nReason: {reason}", color=0xff6b35)
        embed.set_footer(text=f"Case #{case_id}")
        await ctx.send(embed=embed)
    except discord.Forbidden:
        await ctx.send("❌ I don't have permission!")

@bot.command(name="ban")
@commands.has_permissions(ban_members=True)
async def ban_p(ctx, member: discord.Member, *, reason: str = "No reason provided"):
    if not can_act_on(ctx.author, member, ctx.guild):
        await ctx.send("❌ You can't ban this member!")
        return
    try:
        await member.ban(reason=f"{reason} | By {ctx.author}")
        case_id = log_case(ctx.guild.id, 'ban', member, ctx.author, reason)
        await post_case_log(ctx.guild, case_id, 'ban', member, ctx.author, reason)
        embed = discord.Embed(description=f"🔨 **{member}** was banned.\nReason: {reason}", color=0xff0000)
        embed.set_footer(text=f"Case #{case_id}")
        await ctx.send(embed=embed)
    except discord.Forbidden:
        await ctx.send("❌ I don't have permission!")

@bot.command(name="unban")
@commands.has_permissions(ban_members=True)
async def unban_p(ctx, user_id: str, *, reason: str = "No reason provided"):
    try:
        user = await bot.fetch_user(int(user_id))
        await ctx.guild.unban(user, reason=f"{reason} | By {ctx.author}")
        case_id = log_case(ctx.guild.id, 'unban', user, ctx.author, reason)
        await post_case_log(ctx.guild, case_id, 'unban', user, ctx.author, reason)
        embed = discord.Embed(description=f"✅ **{user}** was unbanned.", color=0x00ff00)
        embed.set_footer(text=f"Case #{case_id}")
        await ctx.send(embed=embed)
    except:
        await ctx.send("❌ User not found or not banned!")

@bot.command(name="timeout")
@commands.has_permissions(moderate_members=True)
async def timeout_p(ctx, member: discord.Member, minutes: int, *, reason: str = "No reason provided"):
    if not can_act_on(ctx.author, member, ctx.guild):
        await ctx.send("❌ You can't timeout this member!")
        return
    try:
        await member.timeout(timedelta(minutes=minutes), reason=f"{reason} | By {ctx.author}")
        case_id = log_case(ctx.guild.id, 'timeout', member, ctx.author, reason, duration=minutes)
        await post_case_log(ctx.guild, case_id, 'timeout', member, ctx.author, reason, duration=minutes)
        embed = discord.Embed(description=f"🔇 **{member}** timed out for {minutes} min.\nReason: {reason}", color=0xff6b35)
        embed.set_footer(text=f"Case #{case_id}")
        await ctx.send(embed=embed)
    except discord.Forbidden:
        await ctx.send("❌ I don't have permission!")

@bot.command(name="untimeout")
@commands.has_permissions(moderate_members=True)
async def untimeout_p(ctx, member: discord.Member, *, reason: str = "No reason provided"):
    try:
        await member.timeout(None, reason=f"{reason} | By {ctx.author}")
        case_id = log_case(ctx.guild.id, 'untimeout', member, ctx.author, reason)
        await post_case_log(ctx.guild, case_id, 'untimeout', member, ctx.author, reason)
        embed = discord.Embed(description=f"🔊 Timeout removed from **{member}**.", color=0x00ff00)
        embed.set_footer(text=f"Case #{case_id}")
        await ctx.send(embed=embed)
    except discord.Forbidden:
        await ctx.send("❌ I don't have permission!")

@bot.command(name="mute")
@commands.has_permissions(manage_roles=True)
async def mute_p(ctx, member: discord.Member, *, reason: str = "No reason provided"):
    if not can_act_on(ctx.author, member, ctx.guild):
        await ctx.send("❌ You can't mute this member!")
        return
    role = await get_muted_role(ctx.guild)
    if role in member.roles:
        await ctx.send(f"❌ **{member}** is already muted!")
        return
    try:
        await member.add_roles(role, reason=f"{reason} | By {ctx.author}")
        case_id = log_case(ctx.guild.id, 'mute', member, ctx.author, reason)
        await post_case_log(ctx.guild, case_id, 'mute', member, ctx.author, reason)
        embed = discord.Embed(description=f"🔇 **{member}** was muted.\nReason: {reason}", color=0xff6b35)
        embed.set_footer(text=f"Case #{case_id}")
        await ctx.send(embed=embed)
    except discord.Forbidden:
        await ctx.send("❌ I don't have permission!")

@bot.command(name="unmute")
@commands.has_permissions(manage_roles=True)
async def unmute_p(ctx, member: discord.Member, *, reason: str = "No reason provided"):
    role = discord.utils.get(ctx.guild.roles, name="Muted")
    if role is None or role not in member.roles:
        await ctx.send(f"❌ **{member}** is not muted!")
        return
    try:
        await member.remove_roles(role)
        case_id = log_case(ctx.guild.id, 'unmute', member, ctx.author, reason)
        await post_case_log(ctx.guild, case_id, 'unmute', member, ctx.author, reason)
        embed = discord.Embed(description=f"🔊 **{member}** was unmuted.", color=0x00ff00)
        embed.set_footer(text=f"Case #{case_id}")
        await ctx.send(embed=embed)
    except discord.Forbidden:
        await ctx.send("❌ I don't have permission!")

@bot.command(name="softban")
@commands.has_permissions(ban_members=True)
async def softban_p(ctx, member: discord.Member, *, reason: str = "No reason provided"):
    if not can_act_on(ctx.author, member, ctx.guild):
        await ctx.send("❌ You can't softban this member!")
        return
    try:
        await member.ban(reason=f"Softban: {reason}", delete_message_seconds=86400)
        await ctx.guild.unban(member)
        case_id = log_case(ctx.guild.id, 'softban', member, ctx.author, reason)
        await post_case_log(ctx.guild, case_id, 'softban', member, ctx.author, reason)
        embed = discord.Embed(description=f"🔨 **{member}** was softbanned.\nReason: {reason}", color=0xff6b35)
        embed.set_footer(text=f"Case #{case_id}")
        await ctx.send(embed=embed)
    except discord.Forbidden:
        await ctx.send("❌ I don't have permission!")

@bot.command(name="purge", aliases=["clear"])
@commands.has_permissions(manage_messages=True)
async def purge_p(ctx, amount: int):
    if amount < 1 or amount > 100:
        await ctx.send("❌ Enter 1-100!")
        return
    deleted = await ctx.channel.purge(limit=amount + 1)
    await ctx.send(f"🗑️ Deleted **{len(deleted) - 1}** messages!", delete_after=3)
    log_embed = discord.Embed(description=f"🗑️ **{len(deleted) - 1} messages** purged in {ctx.channel.mention}\nBy: {ctx.author}", color=0xff6b35, timestamp=datetime.utcnow())
    await send_log(ctx.guild, log_embed)

@bot.command(name="history")
@commands.has_permissions(kick_members=True)
async def history_p(ctx, member: discord.Member):
    cases = get_user_cases(ctx.guild.id, member.id)
    if not cases:
        await ctx.send(f"📋 **{member}** has no history!")
        return
    embed = discord.Embed(title=f"📋 History: {member}", color=0xff6b35)
    embed.set_thumbnail(url=member.display_avatar.url)
    for c in cases[-15:][::-1]:
        emoji = ACTION_EMOJIS.get(c['action'], '📌')
        dur = f" ({c['duration']} min)" if c.get('duration') else ""
        embed.add_field(
            name=f"{emoji} Case #{c['case_id']} — {c['action'].title()}{dur}",
            value=f"By: {c['moderator_tag']}\nReason: {c['reason']}\nDate: {c['timestamp'][:10]}",
            inline=False
        )
    embed.set_footer(text=f"Total: {len(cases)} (last 15)")
    await ctx.send(embed=embed)

@bot.command(name="case")
@commands.has_permissions(kick_members=True)
async def case_p(ctx, case_id: int):
    c = get_case_by_id(ctx.guild.id, case_id)
    if not c:
        await ctx.send(f"❌ Case #{case_id} not found!")
        return
    emoji = ACTION_EMOJIS.get(c['action'], '📌')
    dur = f" ({c['duration']} min)" if c.get('duration') else ""
    embed = discord.Embed(title=f"{emoji} Case #{c['case_id']} — {c['action'].title()}{dur}", color=0xff6b35)
    embed.add_field(name="Target", value=c['target_tag'], inline=True)
    embed.add_field(name="Moderator", value=c['moderator_tag'], inline=True)
    embed.add_field(name="Reason", value=c['reason'], inline=False)
    embed.add_field(name="Date", value=c['timestamp'][:19].replace('T', ' '), inline=False)
    await ctx.send(embed=embed)

@bot.command(name="play")
async def play_p(ctx, *, query: str):
    if not ctx.author.voice:
        await ctx.send("❌ Join a voice channel first!")
        return
    vc = ctx.guild.voice_client
    if not vc:
        vc = await ctx.author.voice.channel.connect()
    msg = await ctx.send(f"🔍 Searching: `{query}`...")
    try:
        player = await get_source(query)
    except Exception as e:
        await msg.edit(content=f"❌ Error: {e}")
        return
    await msg.delete()
    data = get_guild_data(ctx.guild.id)
    if vc.is_playing() or vc.is_paused():
        data['queue'].append(player)
        embed = discord.Embed(description=f"📋 Added: **{player.title}** • `#{len(data['queue'])}`", color=0xff6b35)
        await ctx.send(embed=embed, delete_after=5)
    else:
        data['current'] = player
        data['dj'] = ctx.author.id
        vc.play(player, after=lambda e: asyncio.run_coroutine_threadsafe(play_next(ctx.guild, vc, ctx), bot.loop))
        await update_panel(ctx.channel, ctx.guild, vc, is_channel=True)

@bot.command(name="skip")
async def skip_p(ctx):
    vc = ctx.guild.voice_client
    data = get_guild_data(ctx.guild.id)
    if data.get('dj') and ctx.author.id != data['dj']:
        needed = max(1, len([m for m in vc.channel.members if not m.bot]) // 2) if vc else 1
        await ctx.send(f"🗳️ **Vote to skip!** (0/{needed} votes)", view=VoteView('skip', ctx.guild, vc, needed))
        return
    if vc and (vc.is_playing() or vc.is_paused()):
        vc.stop()
        await ctx.send("⏭️ Skipped!", delete_after=3)
    else:
        await ctx.send("❌ Nothing is playing!", delete_after=3)

@bot.command(name="stop")
async def stop_p(ctx):
    data = get_guild_data(ctx.guild.id)
    vc = ctx.guild.voice_client
    if data.get('dj') and ctx.author.id != data['dj']:
        needed = max(1, len([m for m in vc.channel.members if not m.bot]) // 2) if vc else 1
        await ctx.send(f"🗳️ **Vote to stop!** (0/{needed} votes)", view=VoteView('stop', ctx.guild, vc, needed))
        return
    data['queue'].clear()
    data['current'] = None
    data['dj'] = None
    if vc: await vc.disconnect()
    await ctx.send("⏹️ Stopped!", delete_after=3)

@bot.command(name="pause")
async def pause_p(ctx):
    data = get_guild_data(ctx.guild.id)
    if data.get('dj') and ctx.author.id != data['dj']:
        await ctx.send("❌ Only the DJ can pause!")
        return
    vc = ctx.guild.voice_client
    if vc and vc.is_playing():
        vc.pause()
        await ctx.send("⏸️ Paused!", delete_after=3)
    else:
        await ctx.send("❌ Nothing is playing!", delete_after=3)

@bot.command(name="resume")
async def resume_p(ctx):
    data = get_guild_data(ctx.guild.id)
    if data.get('dj') and ctx.author.id != data['dj']:
        await ctx.send("❌ Only the DJ can resume!")
        return
    vc = ctx.guild.voice_client
    if vc and vc.is_paused():
        vc.resume()
        await ctx.send("▶️ Resumed!", delete_after=3)
    else:
        await ctx.send("❌ Not paused!", delete_after=3)

@bot.command(name="queue", aliases=["q"])
async def queue_p(ctx):
    data = get_guild_data(ctx.guild.id)
    q = data['queue']
    if not q:
        await ctx.send("📋 Queue is empty!")
        return
    embed = discord.Embed(title="📋 Queue", color=0xff6b35)
    for i, s in enumerate(q, 1):
        embed.add_field(name=f"{i}.", value=s.title, inline=False)
    await ctx.send(embed=embed)

@bot.command(name="loop")
async def loop_p(ctx):
    data = get_guild_data(ctx.guild.id)
    if data.get('dj') and ctx.author.id != data['dj']:
        await ctx.send("❌ Only the DJ can toggle loop!")
        return
    data['loop'] = not data['loop']
    await ctx.send(f"🔁 Loop {'✅ On' if data['loop'] else '❌ Off'}!", delete_after=3)

@bot.command(name="volume", aliases=["vol"])
async def volume_p(ctx, vol: int):
    data = get_guild_data(ctx.guild.id)
    if data.get('dj') and ctx.author.id != data['dj']:
        await ctx.send("❌ Only the DJ can change volume!")
        return
    vc = ctx.guild.voice_client
    if not vc or not vc.source:
        await ctx.send("❌ Nothing playing!")
        return
    if 0 <= vol <= 100:
        vc.source.volume = vol / 100
        await ctx.send(f"🔊 Volume: **{vol}%**", delete_after=3)
    else:
        await ctx.send("❌ Enter 0-100!")

@bot.command(name="nowplaying", aliases=["np"])
async def np_p(ctx):
    data = get_guild_data(ctx.guild.id)
    if data.get('current'):
        await update_panel(ctx.channel, ctx.guild, ctx.guild.voice_client, is_channel=True)
    else:
        await ctx.send("❌ Nothing is playing!")

@bot.command(name="lyrics")
async def lyrics_p(ctx, *, song: str = None):
    if not song:
        data = get_guild_data(ctx.guild.id)
        cur = data.get('current')
        if not cur:
            await ctx.send("❌ Nothing is playing!")
            return
        song = cur.title
    msg = await ctx.send(f"🔍 Searching lyrics for: **{song}**...")
    result = await asyncio.get_event_loop().run_in_executor(None, lambda: get_lyrics(song))
    if not result:
        await msg.edit(content=f"❌ Lyrics not found for: **{song}**")
        return
    if len(result) > 4000:
        result = result[:4000] + "\n..."
    embed = discord.Embed(title=f"🎵 Lyrics: {song}", description=result, color=0xff6b35)
    await msg.delete()
    await ctx.send(embed=embed)

@bot.command(name="balance", aliases=["bal", "money"])
async def balance_p(ctx, member: discord.Member = None):
    member = member or ctx.author
    econ = get_econ(ctx.guild.id, member.id)
    embed = discord.Embed(title=f"💰 {member.display_name}'s Balance", color=0xff6b35)
    embed.add_field(name="👛 Wallet", value=f"${econ['wallet']:,}", inline=True)
    embed.add_field(name="🏦 Bank", value=f"${econ['bank']:,}", inline=True)
    embed.add_field(name="💎 Total", value=f"${econ['wallet'] + econ['bank']:,}", inline=True)
    embed.set_thumbnail(url=member.display_avatar.url)
    await ctx.send(embed=embed)

@bot.command(name="daily")
async def daily_p(ctx):
    econ = get_econ(ctx.guild.id, ctx.author.id)
    now = datetime.utcnow()
    if econ['last_daily']:
        last = datetime.fromisoformat(econ['last_daily'])
        diff = (now - last).total_seconds()
        if diff < 86400:
            remaining = 86400 - diff
            h, m = divmod(int(remaining), 3600)
            m //= 60
            await ctx.send(f"⏰ Daily already claimed! Come back in **{h}h {m}m**!")
            return
    reward = random.randint(200, 500)
    econ['wallet'] += reward
    econ['last_daily'] = now.isoformat()
    save_econ()
    embed = discord.Embed(description=f"💰 You claimed **${reward:,}** daily reward!\n💛 Balance: **${econ['wallet']:,}**", color=0xffd700)
    await ctx.send(embed=embed)

@bot.command(name="work")
async def work_p(ctx):
    econ = get_econ(ctx.guild.id, ctx.author.id)
    now = datetime.utcnow()
    if econ['last_work']:
        last = datetime.fromisoformat(econ['last_work'])
        diff = (now - last).total_seconds()
        if diff < 3600:
            remaining = 3600 - diff
            m = int(remaining // 60)
            await ctx.send(f"⏰ You're tired! Rest for **{m} minutes**!")
            return
    jobs = ["programmer", "chef", "driver", "teacher", "doctor", "musician"]
    job = random.choice(jobs)
    reward = random.randint(50, 200)
    econ['wallet'] += reward
    econ['last_work'] = now.isoformat()
    save_econ()
    embed = discord.Embed(description=f"💼 You worked as a **{job}** and earned **${reward:,}**!\n💛 Balance: **${econ['wallet']:,}**", color=0x00ff66)
    await ctx.send(embed=embed)

@bot.command(name="deposit", aliases=["dep"])
async def deposit_p(ctx, amount: str):
    econ = get_econ(ctx.guild.id, ctx.author.id)
    amt = econ['wallet'] if amount.lower() == 'all' else int(amount)
    if amt <= 0 or amt > econ['wallet']:
        await ctx.send(f"❌ You only have **${econ['wallet']:,}** in wallet!")
        return
    econ['wallet'] -= amt
    econ['bank'] += amt
    save_econ()
    await ctx.send(embed=discord.Embed(description=f"🏦 Deposited **${amt:,}** to bank!\n👛 Wallet: **${econ['wallet']:,}** | 🏦 Bank: **${econ['bank']:,}**", color=0x00ff66))

@bot.command(name="withdraw", aliases=["with"])
async def withdraw_p(ctx, amount: str):
    econ = get_econ(ctx.guild.id, ctx.author.id)
    amt = econ['bank'] if amount.lower() == 'all' else int(amount)
    if amt <= 0 or amt > econ['bank']:
        await ctx.send(f"❌ You only have **${econ['bank']:,}** in bank!")
        return
    econ['bank'] -= amt
    econ['wallet'] += amt
    save_econ()
    await ctx.send(embed=discord.Embed(description=f"👛 Withdrew **${amt:,}** from bank!\n👛 Wallet: **${econ['wallet']:,}** | 🏦 Bank: **${econ['bank']:,}**", color=0x00ff66))

@bot.command(name="rob")
async def rob_p(ctx, member: discord.Member):
    if member.id == ctx.author.id or member.bot:
        await ctx.send("❌ Invalid target!")
        return
    robber = get_econ(ctx.guild.id, ctx.author.id)
    victim = get_econ(ctx.guild.id, member.id)
    if victim['wallet'] < 100 or robber['wallet'] < 200:
        await ctx.send("❌ Not enough money to rob!")
        return
    if random.random() < 0.4:
        fine = random.randint(100, 300)
        robber['wallet'] = max(0, robber['wallet'] - fine)
        save_econ()
        await ctx.send(embed=discord.Embed(description=f"🚔 Got caught! Paid **${fine:,}** fine!", color=0xff3333))
    else:
        stolen = random.randint(int(victim['wallet'] * 0.1), int(victim['wallet'] * 0.4))
        victim['wallet'] -= stolen
        robber['wallet'] += stolen
        save_econ()
        await ctx.send(embed=discord.Embed(description=f"💰 Robbed **${stolen:,}** from **{member.display_name}**!", color=0x00ff66))

@bot.command(name="pay")
async def pay_p(ctx, member: discord.Member, amount: int):
    if member.id == ctx.author.id or amount <= 0:
        await ctx.send("❌ Invalid!")
        return
    payer = get_econ(ctx.guild.id, ctx.author.id)
    receiver = get_econ(ctx.guild.id, member.id)
    if payer['wallet'] < amount:
        await ctx.send(f"❌ You only have **${payer['wallet']:,}**!")
        return
    payer['wallet'] -= amount
    receiver['wallet'] += amount
    save_econ()
    await ctx.send(embed=discord.Embed(description=f"💸 Paid **${amount:,}** to {member.mention}!", color=0x00ff66))

@bot.command(name="slots")
async def slots_p(ctx, bet: int):
    econ = get_econ(ctx.guild.id, ctx.author.id)
    if bet <= 0 or bet > econ['wallet']:
        await ctx.send(f"❌ Invalid bet! You have **${econ['wallet']:,}**!")
        return
    econ['wallet'] -= bet
    symbols = ['🍒', '🍋', '🍊', '🍇', '⭐', '💎', '7️⃣']
    weights = [30, 25, 20, 15, 5, 3, 2]
    reels = random.choices(symbols, weights=weights, k=3)
    if reels[0] == reels[1] == reels[2]:
        multipliers = {'7️⃣': 50, '💎': 20, '⭐': 10, '🍇': 5, '🍊': 4, '🍋': 3, '🍒': 2}
        mult = multipliers.get(reels[0], 2)
        winnings = bet * mult
        econ['wallet'] += winnings
        result = f"🎉 JACKPOT! **{reels[0]} x3** — Win **${winnings:,}**! (x{mult})"
        color = 0xffd700
    elif reels[0] == reels[1] or reels[1] == reels[2] or reels[0] == reels[2]:
        winnings = int(bet * 1.5)
        econ['wallet'] += winnings
        result = f"✅ Two of a kind! Win **${winnings:,}**!"
        color = 0x00ff66
    else:
        result = f"😢 No match! Lost **${bet:,}**!"
        color = 0xff3333
    save_econ()
    embed = discord.Embed(title="🎰 Slots", color=color)
    embed.add_field(name="Result", value=f"[ {reels[0]} | {reels[1]} | {reels[2]} ]\n{result}", inline=False)
    embed.set_footer(text=f"Balance: ${econ['wallet']:,}")
    await ctx.send(embed=embed)

@bot.command(name="coinflip", aliases=["cf"])
async def coinflip_p(ctx, bet: int, choice: str):
    if choice.lower() not in ['heads', 'tails']:
        await ctx.send("❌ Choose **heads** or **tails**!")
        return
    econ = get_econ(ctx.guild.id, ctx.author.id)
    if bet <= 0 or bet > econ['wallet']:
        await ctx.send(f"❌ Invalid bet! You have **${econ['wallet']:,}**!")
        return
    econ['wallet'] -= bet
    result = random.choice(['heads', 'tails'])
    if result == choice.lower():
        econ['wallet'] += bet * 2
        embed = discord.Embed(description=f"🪙 **{result.title()}**!\n🎉 You won **${bet*2:,}**!\n💰 Balance: **${econ['wallet']:,}**", color=0x00ff66)
    else:
        embed = discord.Embed(description=f"🪙 **{result.title()}**!\n😢 You lost **${bet:,}**!\n💰 Balance: **${econ['wallet']:,}**", color=0xff3333)
    save_econ()
    await ctx.send(embed=embed)

@bot.command(name="bj", aliases=["blackjack"])
async def bj_p(ctx, bet: int):
    econ = get_econ(ctx.guild.id, ctx.author.id)
    if bet <= 0 or bet > econ['wallet']:
        await ctx.send(f"❌ Invalid bet! You have **${econ['wallet']:,}**!")
        return
    key = f"{ctx.guild.id}_{ctx.author.id}"
    if key in active_bj:
        await ctx.send("❌ You already have an active game!")
        return
    econ['wallet'] -= bet
    save_econ()
    deck = make_deck()
    player = [deck.pop(), deck.pop()]
    dealer = [deck.pop(), deck.pop()]
    active_bj[key] = {'player': player, 'dealer': dealer, 'deck': deck}
    pval = hand_value(player)
    embed = discord.Embed(title="🃏 Blackjack", color=0xff6b35)
    embed.add_field(name=f"{ctx.author.display_name}'s Hand", value=f"{hand_str(player)}\nValue: {'Soft ' if is_soft(player) else ''}{pval}", inline=False)
    embed.add_field(name="Dealer Hand", value=f"{hand_str(dealer, hide_second=True)}\nValue: {hand_value([dealer[0]])}", inline=False)
    embed.add_field(name="Cards Remaining", value=f"`{len(deck)}` remaining", inline=False)
    embed.set_footer(text=f"Bet: ${bet:,} | Balance: ${econ['wallet']:,}")
    view = BlackjackView(ctx.guild.id, ctx.author.id, bet)
    await ctx.send(embed=embed, view=view)

@bot.command(name="elb", aliases=["econlb"])
async def econ_lb_p(ctx):
    gid = str(ctx.guild.id)
    if gid not in economy_db or not economy_db[gid]:
        await ctx.send("❌ No data yet!")
        return
    sorted_users = sorted(economy_db[gid].items(), key=lambda x: x[1]['wallet'] + x[1]['bank'], reverse=True)[:10]
    embed = discord.Embed(title="💰 Economy Leaderboard", color=0xffd700)
    medals = ['🥇', '🥈', '🥉']
    for i, (uid, data) in enumerate(sorted_users, 1):
        member = ctx.guild.get_member(int(uid))
        name = member.display_name if member else f"User {uid}"
        medal = medals[i-1] if i <= 3 else f"`{i}.`"
        total = data['wallet'] + data['bank']
        embed.add_field(name=f"{medal} {name}", value=f"💎 **${total:,}** | 👛 ${data['wallet']:,} | 🏦 ${data['bank']:,}", inline=False)
    await ctx.send(embed=embed)

@bot.command(name="help")
async def help_p(ctx):
    embed = discord.Embed(title="📖 Bot Commands (.prefix & /slash)", color=0xff6b35)
    embed.add_field(name="🎵 Music", value="`.play` `.skip` `.stop` `.pause` `.resume` `.q` `.loop` `.vol` `.np` `.lyrics`", inline=False)
    embed.add_field(name="📋 Playlists", value="`/playlist create/add/removesong/remove/play/list/view`", inline=False)
    embed.add_field(name="🛡️ Moderation", value="`.kick` `.ban` `.unban` `.timeout` `.untimeout` `.mute` `.unmute` `.softban` `.purge` `.history` `.case`", inline=False)
    embed.add_field(name="📊 Leveling", value="`.rank [@user]` `.lb`", inline=False)
    embed.add_field(name="🎉 Giveaway", value="`.giveaway <min> <winners> <prize>`", inline=False)
    embed.add_field(name="🎫 Ticket", value="Ticket kanalındakı **Create Ticket** düyməsi", inline=False)
    embed.add_field(name="💰 Economy", value="`.bal` `.daily` `.work` `.dep` `.with` `.rob` `.pay` `.elb`", inline=False)
    embed.add_field(name="🎰 Casino", value="`.bj <bet>` `.slots <bet>` `.cf <bet> heads/tails`", inline=False)
    embed.add_field(name="🎮 Community", value="`.poll <question> <opt1> <opt2>` `.afk [reason]`", inline=False)
    embed.add_field(name="💡 Utility", value="`.ping`", inline=False)
    await ctx.send(embed=embed)

setup_group = app_commands.Group(name="setup", description="Server setup commands")

@setup_group.command(name="log", description="Set the log channel")
@app_commands.describe(channel="Log channel")
@app_commands.checks.has_permissions(manage_guild=True)
async def setup_log(interaction: discord.Interaction, channel: discord.TextChannel):
    s = get_settings(interaction.guild.id)
    s['log'] = str(channel.id)
    save_settings()
    embed = discord.Embed(description=f"✅ Log channel set to {channel.mention}!", color=0x00ff66)
    await interaction.response.send_message(embed=embed)

@setup_group.command(name="ticket", description="Set the ticket panel channel")
@app_commands.describe(channel="Ticket channel")
@app_commands.checks.has_permissions(manage_guild=True)
async def setup_ticket(interaction: discord.Interaction, channel: discord.TextChannel):
    s = get_settings(interaction.guild.id)
    s['ticket'] = str(channel.id)
    save_settings()
    embed = discord.Embed(
        title="🎫 Support Tickets",
        description="Need help? Click below to open a private support ticket!\nStaff will assist you as soon as possible.",
        color=0xff6b35
    )
    await channel.send(embed=embed, view=TicketView())
    embed2 = discord.Embed(description=f"✅ Ticket channel set to {channel.mention}!", color=0x00ff66)
    await interaction.response.send_message(embed=embed2)

@setup_group.command(name="levelup", description="Set the level up announcement channel")
@app_commands.describe(channel="Level up channel")
@app_commands.checks.has_permissions(manage_guild=True)
async def setup_levelup(interaction: discord.Interaction, channel: discord.TextChannel):
    s = get_settings(interaction.guild.id)
    s['levelup'] = str(channel.id)
    save_settings()
    embed = discord.Embed(description=f"✅ Level up channel set to {channel.mention}!", color=0x00ff66)
    await interaction.response.send_message(embed=embed)

@setup_group.command(name="welcome", description="Set the welcome channel")
@app_commands.describe(channel="Welcome channel")
@app_commands.checks.has_permissions(manage_guild=True)
async def setup_welcome(interaction: discord.Interaction, channel: discord.TextChannel):
    s = get_settings(interaction.guild.id)
    s['welcome'] = str(channel.id)
    save_settings()
    embed = discord.Embed(description=f"✅ Welcome channel set to {channel.mention}!", color=0x00ff66)
    await interaction.response.send_message(embed=embed)

@setup_group.command(name="view", description="View current server settings")
@app_commands.checks.has_permissions(manage_guild=True)
async def setup_view(interaction: discord.Interaction):
    s = get_settings(interaction.guild.id)
    embed = discord.Embed(title="⚙️ Server Settings", color=0xff6b35)
    embed.add_field(name="📋 Log Channel", value=f"<#{s['log']}>" if s.get('log') else "❌ Not set", inline=False)
    embed.add_field(name="🎫 Ticket Channel", value=f"<#{s['ticket']}>" if s.get('ticket') else "❌ Not set", inline=False)
    embed.add_field(name="📊 Level Up Channel", value=f"<#{s['levelup']}>" if s.get('levelup') else "❌ Not set", inline=False)
    embed.add_field(name="👋 Welcome Channel", value=f"<#{s['welcome']}>" if s.get('welcome') else "❌ Not set (system channel)", inline=False)
    await interaction.response.send_message(embed=embed)

@setup_group.command(name="reset", description="Reset all server settings")
@app_commands.checks.has_permissions(administrator=True)
async def setup_reset(interaction: discord.Interaction):
    settings_db[str(interaction.guild.id)] = {'log': None, 'ticket': None, 'levelup': None, 'welcome': None}
    save_settings()
    embed = discord.Embed(description="♻️ All settings reset!", color=0xff3333)
    await interaction.response.send_message(embed=embed)

bot.tree.add_command(playlist_group)
bot.tree.add_command(setup_group)
bot.run(os.environ.get("TOKEN", "BURAYA_TOKENINI_YAZ"))
