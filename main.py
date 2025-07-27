import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import datetime
from dismob import log, filehelper

async def setup(bot: commands.Bot):
    log.info("Module `logs` setup")
    filehelper.ensure_directory("db")
    await bot.add_cog(Logs(bot))

async def teardown(bot: commands.Bot):
    log.info("Module `logs` teardown")
    await bot.remove_cog("Logs")

class Logs(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot: commands.Bot = bot
        self.db_path: str = "db/logs.db"
        log.info(f"Cog `logs` initialized")

    async def cog_load(self):
        filehelper.ensure_directory("db")
        await self.setup_db()
        log.info(f"Cog `logs` loaded")

    def cog_unload(self):
        log.info(f"Cog `logs` unloaded")

    async def setup_db(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS log_settings (
                    guild_id INTEGER,
                    log_type TEXT,
                    channel_id INTEGER,
                    enabled INTEGER DEFAULT 1,
                    PRIMARY KEY (guild_id, log_type)
                )
            """)
            await db.commit()

    async def get_log_channel(self, guild_id: int, log_type: str) -> discord.TextChannel | None:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT channel_id, enabled FROM log_settings WHERE guild_id = ? AND log_type = ?",
                (guild_id, log_type)
            )
            result = await cursor.fetchone()
            if result and result[1]:  # Check if enabled
                return self.bot.get_channel(result[0])
            return None

    #####                   #####
    #       Config Commands     #
    #####                   #####

    class LogTypes(str):
        MESSAGES = "messages"
        MEMBERS = "members"
        ROLES = "roles"
        VOICE = "voice"
        NITRO = "nitro"
        TRAFFIC = "traffic"

    LOGS_TYPES = [
        app_commands.Choice(name=LogTypes.MESSAGES, value=LogTypes.MESSAGES),
        app_commands.Choice(name=LogTypes.MEMBERS, value=LogTypes.MEMBERS),
        app_commands.Choice(name=LogTypes.ROLES, value=LogTypes.ROLES),
        app_commands.Choice(name=LogTypes.VOICE, value=LogTypes.VOICE),
        app_commands.Choice(name=LogTypes.NITRO, value=LogTypes.NITRO),
        app_commands.Choice(name=LogTypes.TRAFFIC, value=LogTypes.TRAFFIC),
    ]

    @app_commands.command(name="logs", description="Configure log channels for various events. Display current settings if no parameters are provided.")
    @app_commands.describe(
        log_type="Type of logs to configure",
        channel="Channel where logs will be sent",
        enabled="Enable or disable the logs",
    )
    @app_commands.choices(log_type=LOGS_TYPES)
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_channels=True)
    async def logs_settings(self, interaction: discord.Interaction, log_type: str, channel: discord.TextChannel = None, enabled: bool | None = None):

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT channel_id, enabled FROM log_settings WHERE guild_id = ? AND log_type = ?", (interaction.guild_id, log_type))
            result = await cursor.fetchone()
            old_channel_id = result[0] if result else 0
            old_enabled = result[1] if result else True

            # if no parameters are provided, display current settings
            if channel is None and enabled is None:
                channel_str = f"<#{old_channel_id}>" if old_channel_id else "None"
                enabled_str = "enabled" if old_enabled else "disabled"
                await log.client(interaction, f"Logs settings for {log_type}:\n- Channel set to {channel_str}\n- Logs are {enabled_str}") 
                return
            
            new_channel_id: int = channel.id if channel is not None else old_channel_id
            new_enabled: bool = enabled if enabled is not None else old_enabled

            await db.execute("""
                INSERT INTO log_settings (guild_id, log_type, channel_id, enabled) 
                VALUES (?, ?, ?, ?)
                ON CONFLICT (guild_id, log_type) 
                DO UPDATE SET channel_id = excluded.channel_id, enabled = excluded.enabled""",
                (interaction.guild_id, log_type, new_channel_id, new_enabled)
            )
            await db.commit()

        channel_str: str = f"\n- Channel set to {channel.mention}" if channel is not None else ""
        enabled_str: str = f"\n- Logs {'enabled' if enabled else 'disabled'}" if enabled is not None else ""
        await log.success(interaction, f"Log channel for {log_type} has been updated successfully:{channel_str}{enabled_str}")

    #####                   #####
    #       Event Listeners     #
    #####                   #####

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        log_channel = await self.get_log_channel(member.guild.id, self.LogTypes.TRAFFIC)
        if log_channel:
            embed = discord.Embed(
                title="Member Joined",
                description=f"**Member:** {member.mention}",
                color=discord.Color.green(),
                timestamp=datetime.datetime.now()
            )
            embed.set_author(name=member.display_name, icon_url=member.display_avatar.url)
            await log.safe_send_message(log_channel, embed=embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        log_channel = await self.get_log_channel(member.guild.id, self.LogTypes.TRAFFIC)
        if log_channel:
            embed = discord.Embed(
                title="Member Left",
                description=f"**Member:** {member.mention}",
                color=discord.Color.red(),
                timestamp=datetime.datetime.now()
            )
            embed.set_author(name=member.display_name, icon_url=member.display_avatar.url)
            await log.safe_send_message(log_channel, embed=embed)

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if message.author.bot or message.guild is None:
            return

        log_channel = await self.get_log_channel(message.guild.id, self.LogTypes.MESSAGES)
        if log_channel:
            embed = discord.Embed(
                title="Message Deleted",
                color=discord.Color.red(),
                timestamp=datetime.datetime.now()
            )
            embed.add_field(name="Channel", value=message.channel.mention, inline=True)
            embed.add_field(name="Jump Link", value=f"[Jump to Message](https://discord.com/channels/{message.guild.id}/{message.channel.id}/{message.id})", inline=True)
            embed.add_field(name="Content", value=message.content, inline=False)
            embed.set_author(name=message.author.display_name, icon_url=message.author.display_avatar.url)
            await log.safe_send_message(log_channel, embed=embed)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if before.author.bot or before.content == after.content or before.guild is None:
            return

        log_channel = await self.get_log_channel(before.guild.id, self.LogTypes.MESSAGES)
        if log_channel:
            embed = discord.Embed(
                title="Message Edited",
                color=discord.Color.blue(),
                timestamp=datetime.datetime.now()
            )
            embed.add_field(name="Channel", value=before.channel.mention, inline=True)
            embed.add_field(name="Jump Link", value=f"[Jump to Message](https://discord.com/channels/{before.guild.id}/{before.channel.id}/{before.id})", inline=True)
            embed.add_field(name="Before", value=before.content, inline=False)
            embed.add_field(name="After", value=after.content, inline=False)
            embed.set_author(name=before.author.display_name, icon_url=before.author.display_avatar.url)
            await log.safe_send_message(log_channel, embed=embed)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        await self.on_profile_update(before, after, guilds=[before.guild])

    @commands.Cog.listener()
    async def on_user_update(self, before: discord.User, after: discord.User):
        await self.on_profile_update(before, after, guilds=before.mutual_guilds)

    async def send_message_to_all_guilds(self, log_type: str, guilds: list[discord.Guild], embed: discord.Embed):
        if guilds is None or not guilds:
            log.warning("No guilds provided for sending message.")
            return
        
        for guild in guilds:
            log_channel = await self.get_log_channel(guild.id, log_type)
            if log_channel:
                await log.safe_send_message(log_channel, embed=embed)

    async def on_profile_update(self, before: discord.Member | discord.User, after: discord.Member | discord.User, guilds: list[discord.Guild] = []):
        isMember: bool = isinstance(before, discord.Member) and isinstance(after, discord.Member)

        if before.display_name != after.display_name:
            log.debug(f"Display name changed for {before} (send to guilds: {guilds})")
            embed = discord.Embed(
                title="Display Name Changed",
                description=f"**Member:** {before.mention}",
                color=discord.Color.blue(),
                timestamp=datetime.datetime.now()
            )
            embed.add_field(name="Before", value=before.display_name, inline=True)
            embed.add_field(name="After", value=after.display_name, inline=True)
            await self.send_message_to_all_guilds(self.LogTypes.MEMBERS, guilds, embed)

        if isMember and before.roles != after.roles:
            log_channel = await self.get_log_channel(before.guild.id, self.LogTypes.ROLES)
            if log_channel:
                added_roles = set(after.roles) - set(before.roles)
                removed_roles = set(before.roles) - set(after.roles)
                if added_roles or removed_roles:
                    embed = discord.Embed(
                        title="Member Roles Updated",
                        description=f"**Member:** {before.mention}",
                        color=discord.Color.blue(),
                        timestamp=datetime.datetime.now()
                    )
                    if added_roles:
                        embed.add_field(name="Added Roles", value=", ".join(role.mention for role in added_roles), inline=False)
                    if removed_roles:
                        embed.add_field(name="Removed Roles", value=", ".join(role.mention for role in removed_roles), inline=False)
                    await log.safe_send_message(log_channel, embed=embed)

        if before.display_avatar != after.display_avatar:
            log.debug(f"Avatar changed for {before} (send to guilds: {guilds})")
            embed = discord.Embed(
                title="Avatar Changed",
                description=f"**Member:** {before.mention}",
                color=discord.Color.blue(),
                timestamp=datetime.datetime.now()
            )
            embed.set_author(name=after.display_name, icon_url=after.display_avatar.url)
            embed.set_thumbnail(url=after.display_avatar.url)
            await self.send_message_to_all_guilds(self.LogTypes.MEMBERS, guilds, embed)

        if isMember and before.premium_since != after.premium_since:
            log_channel = await self.get_log_channel(before.guild.id, self.LogTypes.MEMBERS)
            if log_channel:
                embed = discord.Embed(
                    title="Nitro Status Changed",
                    description=f"**Member:** {before.mention}",
                    color=discord.Color.blue(),
                    timestamp=datetime.datetime.now()
                )
                if after.premium_since:
                    embed.add_field(name="Nitro Boosted Since", value=after.premium_since.strftime("%Y-%m-%d %H:%M:%S"), inline=False)
                else:
                    embed.add_field(name="Nitro Boosted", value="No longer boosted", inline=False)
                await log.safe_send_message(log_channel, embed=embed)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if before.channel != after.channel:
            log_channel = await self.get_log_channel(member.guild.id, self.LogTypes.VOICE)
            if log_channel:
                embed = discord.Embed(
                    title="Voice Update",
                    description=f"**Member:** {member.mention}",
                    color=discord.Color.blue(),
                    timestamp=datetime.datetime.now()
                )
                embed.add_field(name="Before", value=before.channel.mention if before.channel else "None", inline=True)
                embed.add_field(name="After", value=after.channel.mention if after.channel else "None", inline=True)
                await log.safe_send_message(log_channel, embed=embed)
