"""
Discord Bot Commands for TF System Integration

"""

import discord
from discord.ext import commands
from discord import app_commands
import os
from groq import Groq
import json
import asyncio
from dotenv import load_dotenv

# Load .env from parent bot directory
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
load_dotenv(env_path)
print(f"[TF Commands] Loaded .env from: {env_path}")

# Import the TF API client (from parent directory)
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tf_api_client import TFSystemAPI

# Get Groq configuration from environment
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
GROQ_MODEL = os.getenv('GROQ_MODEL', 'llama-3.3-70b-versatile')
ALLOWED_GUILD_ID = os.getenv('ALLOWED_GUILD_ID')

# Debug: Show which model is being used
print(f"[TF Commands] Using Groq model: {GROQ_MODEL}")

# Initialize Groq client
groq_client = Groq(api_key=GROQ_API_KEY)

# Initialize TF System API
tf_api = TFSystemAPI(
    api_url=os.getenv('TF_SYSTEM_API_URL'),
    api_key=os.getenv('TF_SYSTEM_API_KEY')
)

# Define allowed roles (Commander, Marshal, General)
ALLOWED_ROLES = ['Staff Team', 'Prospect', 'Commander', 'Marshal', 'General']
GENERAL_ROLE_ID = 729817672585314305
DEVELOPER_DISCORD_ID = 751920066332721152
STRIKE_CHANNEL_ID = int(os.getenv('STRIKE_CHANNEL_ID', '986722806442127430'))

# 986722806442127430
def is_developer():
    """Decorator to restrict diagnostic commands to the platform developer."""
    async def predicate(interaction: discord.Interaction):
        if interaction.user.id != DEVELOPER_DISCORD_ID:
            await interaction.response.send_message(
                "❌ This command is restricted to the platform developer.",
                ephemeral=True
            )
            return False
        return True

    return app_commands.check(predicate)



def has_tf_permissions():
    """Decorator to check if user has permission to manage TF"""
    async def predicate(interaction: discord.Interaction):
        # Check if user has any of the allowed roles
        user_roles = [role.name for role in interaction.user.roles]
        has_permission = any(role in ALLOWED_ROLES for role in user_roles)
        
        if not has_permission:
            await interaction.response.send_message(
                "❌ You don't have permission to use this command. "
                f"Required roles: {', '.join(ALLOWED_ROLES)}",
                ephemeral=True
            )
            return False
        
        return True
    
    return app_commands.check(predicate)


def has_general_role():
    """Decorator to check if user has the General role (ID: 729817672585314305 or name 'General')"""
    async def predicate(interaction: discord.Interaction):
        if not hasattr(interaction.user, 'roles'):
            await interaction.response.send_message(
                "❌ You don't have permission to use this command.",
                ephemeral=True
            )
            return False

        has_role = any(
            role.id == GENERAL_ROLE_ID or role.name.lower() == "general"
            for role in interaction.user.roles
        )
        if not has_role:
            await interaction.response.send_message(
                "❌ This command is restricted to members with the **General** role.",
                ephemeral=True
            )
            return False
        return True

    return app_commands.check(predicate)


async def build_dynamic_system_prompt() -> str:
    """Build system prompt dynamically by consulting the TF System API for activities and ranks."""
    # 1. Fetch dynamic activities from API
    try:
        activity_types = await tf_api.get_activity_types()
    except Exception:
        activity_types = []

    if activity_types:
        act_lines = []
        valid_act_names = []
        for act in activity_types:
            name = act.get("name", "")
            pts = act.get("points", 0.0)
            pts_str = f"{int(pts)}" if pts == int(pts) else f"{pts}"
            limited_str = " (only 1 per cycle)" if act.get("is_limited") else ""
            act_lines.append(f"- {name}: {pts_str} points{limited_str}")
            valid_act_names.append(name)
        activities_text = "\n".join(act_lines)
        valid_activities_text = ", ".join(valid_act_names)
    else:
        activities_text = (
            "- Mission: 0.5 points\n"
            "- Supervision: 1 point\n"
            "- Training: 1 point\n"
            "- Raid or Patrol: 1.5 points\n"
            "- Tryout: 1.5 points\n"
            "- Tryout Certification: 1 point (host only)\n"
            "- Cancelled Training: 0.5 points (only 1 per cycle)\n"
            "- Cancelled Tryout: 0.5 points (only 1 per cycle)\n"
            "- Tryout Grading: 0.5 points (only 1 per cycle)\n"
            "- Dueling Supervision/Evaluation: 0.5 points (only 1 per cycle)\n"
            "- Joint Combat Training (JCT): 1.5 points"
        )
        valid_activities_text = "Raid, Patrol, Training, Mission, Supervision, Tryout, Tryout Certification, Cancelled Training, Cancelled Tryout, Tryout Grading, Dueling Supervision/Evaluation, Joint Combat Training"

    # 2. Fetch dynamic ranks/quotas from API
    try:
        quotas = await tf_api.get_rank_quotas()
    except Exception:
        quotas = []

    try:
        ranks_res = await tf_api.get_ranks()
    except Exception:
        ranks_res = {}

    rank_names = []
    if ranks_res and ranks_res.get("success"):
        rank_names = [r.get("rank_name") for r in ranks_res.get("ranks", []) if r.get("rank_name")]
    if not rank_names and quotas:
        rank_names = [q.get("rank_name") for q in quotas if q.get("rank_name")]
    if not rank_names:
        rank_names = ["Aspirant", "Novice", "Adept", "Crusader", "Paladin", "Exemplar", "Prospect", "Commander", "Marshal", "General", "Chief General"]

    valid_ranks_text = ", ".join(rank_names)

    return f"""You are a command parser for a Taskforce Management System.
Parse user commands and extract the intent and entities.

Valid actions:
- change_rank: Change a member's rank
- get_member_info: Get information about a member
- list_members: List all members or filter by rank
- add_member: Add a new member
- remove_member: Remove a member
- log_activity: Log one activity for a member (single entry)
- bulk_log_activity: Log multiple activities of the same type for one member (quantity > 1)
- remove_activity: Remove the most-recent activity of a given type for a member (quantity = 1)
- bulk_remove_activity: Remove multiple activities of the same type for a member (quantity > 1)
- count_activities: Count how many activities of a type a member has
- check_points: Check a member's current AC points and quota progress
- list_activities: List all valid activity types and their point values
- list_quotas: List all rank quota requirements

Activity Types and Points (live from system):
{activities_text}

Valid ranks: {valid_ranks_text}
Valid activity types: {valid_activities_text}

IMPORTANT: Recognize these variations for listing members:
- "show all members" -> list_members with no rank filter
- "list all members" -> list_members with no rank filter
- "show all [rank]" -> list_members with rank filter (e.g., "show all generals" -> rank: "General")
- "list all [rank]s" -> list_members with rank filter (e.g., "list all commanders" -> rank: "Commander")
- "show [rank]s" -> list_members with rank filter
- "list generals" -> list_members with rank: "General"
- "show commanders" -> list_members with rank: "Commander"
- "what rank is [member name]" -> get_member_info with member name
- "what rank is [member name]" -> get_member_info, look up for members with similar letters, people may use nicknames, if i say "slater" i refer to slaterjl2006 for example

IMPORTANT: Activity & Quota Queries
- "what activities can I log?", "list activities", "show activity points", "what are the activities?" -> list_activities
- "what are the quotas?", "list quotas", "show quota requirements", "how many points do ranks need?" -> list_quotas

Note: Always use SINGULAR form of rank names (General, not Generals; Commander, not Commanders)

CRITICAL: Activity Type Spelling
- Match user speech to the closest valid activity type name listed above.
- "cancelled training" or "canceled training" -> MUST map to "Cancelled Training"
- "cancelled tryout" or "canceled tryout" -> MUST map to "Cancelled Tryout"
- "tryout grading" -> MUST map to "Tryout Grading"
- "dueling supervision" or "evaluation" or "dueling evaluation" -> MUST map to "Dueling Supervision/Evaluation"
- "tryout certification" or "tryout cert" -> MUST map to "Tryout Certification"
- "supervision" -> MUST map to "Supervision"
- "jct" or "joint combat" -> MUST map to "Joint Combat Training"
- This is extremely important for the database to recognize the activity.

IMPORTANT: Single vs Bulk Activity Logging
- When the user says "log a training for John" -> log_activity, quantity omitted
- When the user says "log 4 trainings for John" or "log 4x training for John" -> bulk_log_activity, quantity: 4
- When the user says "log 8 missions for Sarah" -> bulk_log_activity, quantity: 8
- Rule: if a number > 1 is mentioned, use bulk_log_activity with that quantity.
- The "quantity" field is always an integer >= 1.

IMPORTANT: Activity Removal Recognition
- "remove training for John" -> remove_activity, activity_type: "Training", quantity: 1
- "undo raid for Sarah" -> remove_activity, activity_type: "Raid", quantity: 1
- "remove 3 trainings for John" or "undo 3 trainings from John" -> bulk_remove_activity, activity_type: "Training", quantity: 3
- "delete 5 missions from Bob" -> bulk_remove_activity, activity_type: "Mission", quantity: 5
- "remove activity from [member]" with no type -> remove_activity with activity_type omitted
- Rule: if a number > 1 is mentioned, use bulk_remove_activity.

IMPORTANT: Count Activity Recognition
- "how many trainings does John have" -> count_activities, member_name: "John", activity_type: "Training"
- "how many missions has Sarah done" -> count_activities, member_name: "Sarah", activity_type: "Mission"
- "count raids for Bob" -> count_activities, member_name: "Bob", activity_type: "Raid"
- "how many activities does X have" -> count_activities, member_name: "X" (no activity_type = show all)
- Optional: "this period" or "this cycle" -> period_only: true

IMPORTANT: Check Points Recognition
- "how many points do I have" -> check_points with no member name
- "what are my points" -> check_points with no member name
- "check my progress" -> check_points with no member name
- "how many points does [member] have" -> check_points with member name
- "what are [member]'s points" -> check_points with member name
- "check points for [member]" -> check_points with member name

Examples of correct parsing:
1.  "show all generals" -> {{"action": "list_members", "parameters": {{"rank": "General"}}}}
2.  "change John to Commander" -> {{"action": "change_rank", "parameters": {{"member_name": "John", "new_rank": "Commander"}}}}
3.  "log a cancelled training for Clicky" -> {{"action": "log_activity", "parameters": {{"member_name": "Clicky", "activity_type": "Cancelled Training"}}}}
4.  "log 4 trainings for John" -> {{"action": "bulk_log_activity", "parameters": {{"member_name": "John", "activity_type": "Training", "quantity": 4}}}}
5.  "log 8 missions for Sarah" -> {{"action": "bulk_log_activity", "parameters": {{"member_name": "Sarah", "activity_type": "Mission", "quantity": 8}}}}
6.  "remove training for John" -> {{"action": "remove_activity", "parameters": {{"member_name": "John", "activity_type": "Training"}}}}
7.  "undo raid for Sarah" -> {{"action": "remove_activity", "parameters": {{"member_name": "Sarah", "activity_type": "Raid"}}}}
8.  "remove 3 trainings from John" -> {{"action": "bulk_remove_activity", "parameters": {{"member_name": "John", "activity_type": "Training", "quantity": 3}}}}
9.  "delete 5 missions from Bob" -> {{"action": "bulk_remove_activity", "parameters": {{"member_name": "Bob", "activity_type": "Mission", "quantity": 5}}}}
10. "how many trainings does John have" -> {{"action": "count_activities", "parameters": {{"member_name": "John", "activity_type": "Training"}}}}
11. "count raids for Sarah this cycle" -> {{"action": "count_activities", "parameters": {{"member_name": "Sarah", "activity_type": "Raid", "period_only": true}}}}
12. "how many activities does Bob have" -> {{"action": "count_activities", "parameters": {{"member_name": "Bob"}}}}
13. "how many points does John have" -> {{"action": "check_points", "parameters": {{"member_name": "John"}}}}
14. "what activities can I log?" -> {{"action": "list_activities", "parameters": {{}}}}
15. "what are the quotas?" -> {{"action": "list_quotas", "parameters": {{}}}}

Respond ONLY with a JSON object in this format:
{{
  "action": "action_name",
  "parameters": {{
    "member_name": "extracted name",
    "new_rank": "rank name",
    "rank": "rank filter",
    "activity_type": "activity type",
    "quantity": 1,
    "period_only": false
  }},
  "confidence": 0.0-1.0
}}

If you can't parse the command, set action to "unknown" and explain in a "reason" field."""


async def parse_intent_with_groq(user_message: str) -> dict:
    """
    Use Groq AI to parse user intent and extract entities
    
    Args:
        user_message: The user's natural language command
    
    Returns:
        dict: Parsed intent with action, parameters, etc.
    """
    system_prompt = await build_dynamic_system_prompt()


    try:
        completion = groq_client.chat.completions.create(
            model=GROQ_MODEL,  # Use model from environment variable
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            temperature=0.1,
            max_tokens=500
        )
        
        response_text = completion.choices[0].message.content
        
        # Extract JSON from response (in case there's extra text)
        json_start = response_text.find('{')
        json_end = response_text.rfind('}') + 1
        if json_start != -1 and json_end != 0:
            response_text = response_text[json_start:json_end]
        
        intent = json.loads(response_text)
        return intent
        
    except Exception as e:
        # Log the error for debugging but don't expose technical details to users
        print(f"Error parsing intent with Groq: {e}")
        return {
            "action": "unknown",
            "reason": "I had trouble understanding that command",
            "confidence": 0.0
        }



class ResponseHandler:
    """Abstracts the difference between Interaction and Message responses"""
    def __init__(self, context, is_interaction=True):
        self.context = context
        self.is_interaction = is_interaction

    async def send(self, content=None, embed=None):
        if self.is_interaction:
            # For interactions, use followup (assumes defer was called)
            await self.context.followup.send(content=content, embed=embed)
        else:
            # For messages, use channel.send
            await self.context.channel.send(content=content, embed=embed)

    @property
    def user(self):
        return self.context.user if self.is_interaction else self.context.author

    @property
    def guild_id(self):
        if self.is_interaction:
            return str(self.context.guild_id or (self.context.guild.id if self.context.guild else ''))
        return str(self.context.guild.id if self.context.guild else '')


class TFSystemCog(commands.Cog):
    """Cog for TF System management commands"""
    
    def __init__(self, bot):
        self.bot = bot
    
    # Helper to check permissions synchronously for message events
    def check_permissions(self, user):
        if not hasattr(user, 'roles'):
            return False
        user_roles = [role.name for role in user.roles]
        return any(role in ALLOWED_ROLES for role in user_roles)

    def check_general_permissions(self, user):
        """Check if user has General role (ID: 729817672585314305 or name 'General')"""
        if not hasattr(user, 'roles'):
            return False
        return any(
            role.id == GENERAL_ROLE_ID or role.name.lower() == "general"
            for role in user.roles
        )

    async def check_action_permission(self, handler: ResponseHandler, action: str) -> bool:
        """Check caller authorization dynamically using their Discord server roles and sector rank permissions."""
        user = handler.user
        if getattr(user, 'id', None) == DEVELOPER_DISCORD_ID:
            return True
        guild = getattr(handler.context, 'guild', None)
        if guild and getattr(user, 'guild_permissions', None) and user.guild_permissions.administrator:
            return True
        if guild and guild.owner_id == user.id:
            return True

        user_roles = [role.name for role in getattr(user, 'roles', []) if role.name != '@everyone']
        guild_id = handler.guild_id

        if guild_id:
            try:
                res = await tf_api.check_permission(
                    discord_user_id=str(user.id),
                    action=action,
                    guild_id=guild_id,
                    roles=user_roles
                )
                if res.get('success'):
                    if res.get('allowed'):
                        return True
                    else:
                        reason = res.get('reason') or f"You do not have permission for '{action}' in this sector."
                        await handler.send(f"❌ {reason}")
                        return False
            except Exception as e:
                print(f"[TF Commands] Error checking dynamic permissions: {e}")

        # Fallback to local role names (e.g. if API is unreachable)
        if action == 'view_data':
            return True
        if action in ['promote', 'delete_activity', 'manage_ac'] and any(getattr(r, 'name', '').lower() in ['general', 'marshal', 'commander'] or getattr(r, 'id', 0) == GENERAL_ROLE_ID for r in getattr(user, 'roles', [])):
            return True
        if action == 'log_activity' and any(role in ALLOWED_ROLES for role in user_roles):
            return True

        await handler.send(f"❌ You do not have permission to perform this action in this sector.")
        return False

    async def _resolve_guild_access(self, guild_id) -> bool:
        """Verify guild access and configure tf_api tenant scope for this guild."""
        if not guild_id:
            return not bool(ALLOWED_GUILD_ID)
        guild_id_str = str(guild_id)
        if ALLOWED_GUILD_ID and guild_id_str == str(ALLOWED_GUILD_ID):
            tf_api.set_tenant(discord_group_id=guild_id_str)
            return True
        try:
            grp_res = await tf_api.get_group_by_discord_id(guild_id_str)
            if grp_res.get('success'):
                tf_api.set_tenant(discord_group_id=guild_id_str)
                return True
        except Exception as e:
            print(f"[TF Commands] Error resolving guild tenant for {guild_id_str}: {e}")
        return False

    @commands.Cog.listener()
    async def on_message(self, message):
        # Ignore messages from self
        if message.author == self.bot.user:
            return

        # Check if bot is mentioned
        if self.bot.user.mentioned_in(message) and not message.mention_everyone:
            # Check if bot has permission to send messages in this channel
            if message.guild:
                permissions = message.channel.permissions_for(message.guild.me)
                if not permissions.send_messages:
                    return
            
            # Check for allowed guild or multi-tenant sector guild
            if message.guild and not await self._resolve_guild_access(message.guild.id):
                return
            # Clean content: remove mention
            content = message.content.replace(f'<@{self.bot.user.id}>', '').strip()
            # Also handle nickname mentions if any
            content = content.replace(f'<@!{self.bot.user.id}>', '').strip()
            
            if not content:
                await message.channel.send("👋 Hello! How can I help you with the Taskforce System?")
                return

            # Show typing indicator (with fallback if typing fails)
            handler = ResponseHandler(message, is_interaction=False)
            command_executed = False
            try:
                async with message.channel.typing():
                    command_executed = True
                    await self.process_command(handler, content)
            except discord.Forbidden:
                print(f"Permission error: Cannot type/send messages in channel {message.channel.id} ({message.channel.name if hasattr(message.channel, 'name') else 'DM'})")
            except Exception as e:
                if not command_executed:
                    print(f"Typing indicator failed ({e}). Attempting to run command without typing...")
                    try:
                        await self.process_command(handler, content)
                    except Exception as inner_e:
                        import traceback
                        print(f"Error in on_message handler (without typing): {inner_e}")
                        traceback.print_exc()
                    else:
                        pass
                else:
                    import traceback
                    print(f"Error in on_message handler: {e}")
                    traceback.print_exc()

    @app_commands.command(name="tf", description="Natural language TF management command")
    @has_tf_permissions()
    async def tf_command(self, interaction: discord.Interaction, command: str):
        if not await self._resolve_guild_access(interaction.guild_id):
            await interaction.response.send_message(
                "❌ This bot is restricted to configured sector servers.",
                ephemeral=True
            )
            return

        await interaction.response.defer()  # Processing may take a moment
        handler = ResponseHandler(interaction, is_interaction=True)
        await self.process_command(handler, command)

    @app_commands.command(name="activities", description="Consult active Taskforce activities and point values (General only)")
    @has_general_role()
    async def slash_activities(self, interaction: discord.Interaction):
        if not await self._resolve_guild_access(interaction.guild_id):
            await interaction.response.send_message(
                "❌ This bot is restricted to configured sector servers.",
                ephemeral=True
            )
            return

        await interaction.response.defer()
        handler = ResponseHandler(interaction, is_interaction=True)
        await self._handle_list_activities(handler)

    @app_commands.command(name="quotas", description="Consult Taskforce rank quota requirements (General only)")
    @has_general_role()
    async def slash_quotas(self, interaction: discord.Interaction):
        if not await self._resolve_guild_access(interaction.guild_id):
            await interaction.response.send_message(
                "❌ This bot is restricted to configured sector servers.",
                ephemeral=True
            )
            return

        await interaction.response.defer()
        handler = ResponseHandler(interaction, is_interaction=True)
        await self._handle_list_quotas(handler)

    @app_commands.command(name="strike", description="Post a strike notice to the designated strikes channel (General only)")
    @app_commands.describe(message="The strike message to log")
    @has_general_role()
    async def slash_strike(self, interaction: discord.Interaction, message: str):
        if not await self._resolve_guild_access(interaction.guild_id):
            await interaction.response.send_message(
                "❌ This bot is restricted to configured sector servers.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        channel = self.bot.get_channel(STRIKE_CHANNEL_ID)
        if not channel:
            try:
                channel = await self.bot.fetch_channel(STRIKE_CHANNEL_ID)
            except Exception as e:
                await interaction.followup.send(
                    f"❌ Unable to find or access the strikes channel (ID: {STRIKE_CHANNEL_ID}): {e}",
                    ephemeral=True
                )
                return

        # Support escaped \n as real line breaks
        formatted_message = message.replace('\\n', '\n')

        try:
            sent_msg = await channel.send(content=formatted_message)
            await interaction.followup.send(
                f"✅ Strike notice posted to {channel.mention}!\n[View Message]({sent_msg.jump_url})",
                ephemeral=True
            )
        except discord.Forbidden:
            await interaction.followup.send(
                f"❌ Bot does not have permissions to post in {channel.mention}.",
                ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(
                f"❌ Error sending strike notice: {e}",
                ephemeral=True
            )


    @app_commands.command(name="tenant", description="Verify the Nexus sector/tenant identified for this Discord server (Developer only)")
    @is_developer()
    async def slash_tenant(self, interaction: discord.Interaction):
        """Slash command to verify the active multi-tenant sector mapped to this Discord server."""
        await interaction.response.defer(ephemeral=True)
        handler = ResponseHandler(interaction, is_interaction=True)
        await self._handle_check_tenant(handler)

    @app_commands.command(name="sector", description="Verify the Nexus sector/tenant identified for this Discord server (Developer only)")
    @is_developer()
    async def slash_sector(self, interaction: discord.Interaction):
        """Alias for /tenant command"""
        await self.slash_tenant(interaction)

    async def _handle_check_tenant(self, handler: ResponseHandler):
        """Build and send a diagnostic embed showing the identified tenant/sector for the guild."""
        if getattr(handler.user, 'id', None) != DEVELOPER_DISCORD_ID:
            await handler.send("❌ This diagnostic command is restricted to the platform developer.")
            return

        guild = getattr(handler.context, 'guild', None)
        guild_id_str = handler.guild_id
        guild_name = guild.name if guild else "Direct Message / Unknown"

        try:
            grp_res = await tf_api.get_group_by_discord_id(guild_id_str)
            status_res = await tf_api.get_status(guild_id=guild_id_str)
        except Exception as e:
            await handler.send(f"❌ Failed to query Nexus API: {e}")
            return

        if grp_res.get('success') and grp_res.get('group'):
            group = grp_res.get('group')
            group_id = group.get('id')
            group_name = group.get('name')
            roblox_group_id = group.get('roblox_group_id') or 'Not Configured'
            discord_group_id = group.get('discord_group_id') or 'Not Configured'
            description = group.get('description') or 'No description provided.'
            member_count = status_res.get('total_members', 'N/A')
            db_status = status_res.get('database', 'unknown')
            roblox_sync = status_res.get('roblox_sync', 'unknown')

            embed = discord.Embed(
                title=f"🛡️ Nexus Sector Identified: {group_name}",
                description=f"This Discord server is officially registered and routed to **Sector {group_id}**.",
                color=discord.Color.from_rgb(168, 85, 247),
                timestamp=discord.utils.utcnow()
            )
            embed.add_field(name="🏛️ Sector Name", value=f"**{group_name}**", inline=True)
            embed.add_field(name="🆔 System Tenant ID", value=f"`{group_id}`", inline=True)
            embed.add_field(name="👥 Active Personnel", value=f"`{member_count}` registered", inline=True)
            embed.add_field(name="🟥 Roblox Group ID", value=f"`{roblox_group_id}`", inline=True)
            embed.add_field(name="💬 Discord Server ID", value=f"`{discord_group_id}`", inline=True)
            embed.add_field(name="⚡ API Database", value=f"`{db_status.upper()}`", inline=True)
            embed.add_field(name="🔄 Roblox Sync", value=f"`{roblox_sync.upper()}`", inline=True)
            embed.add_field(name="📝 Description", value=description, inline=False)
            embed.set_footer(text=f"Nexus Multi-Tenant System • Guild: {guild_name} ({guild_id_str})")
            await handler.send(embed=embed)
        else:
            is_legacy_default = (ALLOWED_GUILD_ID and str(ALLOWED_GUILD_ID) == guild_id_str)
            if is_legacy_default:
                embed = discord.Embed(
                    title="🛡️ Nexus Default Tenant (Fallback)",
                    description=f"This server matches the default `ALLOWED_GUILD_ID` and is mapped to **Tenant 1 (Taskforce)**.",
                    color=discord.Color.from_rgb(56, 189, 248),
                    timestamp=discord.utils.utcnow()
                )
                embed.add_field(name="🏛️ Sector Name", value="**Taskforce (Default)**", inline=True)
                embed.add_field(name="🆔 System Tenant ID", value="`1`", inline=True)
                embed.add_field(name="💬 Discord Server ID", value=f"`{guild_id_str}`", inline=True)
                embed.set_footer(text=f"Nexus System • Guild: {guild_name}")
                await handler.send(embed=embed)
            else:
                embed = discord.Embed(
                    title="⚠️ Unregistered Discord Server",
                    description=f"No sector in the Nexus database is configured for Discord Server ID: `{guild_id_str}`.",
                    color=discord.Color.from_rgb(239, 68, 68),
                    timestamp=discord.utils.utcnow()
                )
                embed.add_field(name="💬 Current Server", value=f"**{guild_name}** (`{guild_id_str}`)", inline=False)
                embed.add_field(
                    name="🔧 How to Link this Server",
                    value=(
                        "1. Open the **Nexus Web Portal**.\n"
                        "2. Go to **Sector Settings** (`/group/settings`).\n"
                        f"3. In the **Discord Server ID** field, enter `{guild_id_str}` and save.\n"
                        "4. Run `/tenant` again to confirm identification."
                    ),
                    inline=False
                )
                embed.set_footer(text="Nexus Multi-Tenant System • Unmapped Guild")
                await handler.send(embed=embed)

    async def process_command(self, handler: ResponseHandler, command_text: str):
        """Unified command processing logic"""
        try:
            # Parse intent using Groq
            intent = await parse_intent_with_groq(command_text)
            
            if intent['action'] == 'unknown':
                # Just return a simple error message instead of chatting
                await handler.send("❌ I didn't understand that command. Try rephrasing you request, or contacting a General for support.")
                return
            
            # Execute based on action using dynamic sector rank permissions
            action_perm_map = {
                'change_rank': 'promote',
                'add_member': 'promote',
                'remove_member': 'promote',
                'log_activity': 'log_activity',
                'bulk_log_activity': 'log_activity',
                'remove_activity': 'delete_activity',
                'bulk_remove_activity': 'delete_activity',
                'list_activities': 'view_data',
                'list_quotas': 'view_data',
            }

            required_perm = action_perm_map.get(intent['action'])
            if required_perm:
                if not await self.check_action_permission(handler, required_perm):
                    return

            if intent['action'] == 'change_rank':
                await self._handle_change_rank(handler, intent['parameters'])
                
            elif intent['action'] == 'get_member_info':
                await self._handle_get_member_info(handler, intent['parameters'])
            
            elif intent['action'] == 'list_members':
                await self._handle_list_members(handler, intent['parameters'])
            
            elif intent['action'] == 'add_member':
                await self._handle_add_member(handler, intent['parameters'])
            
            elif intent['action'] == 'remove_member':
                await self._handle_remove_member(handler, intent['parameters'])
            
            elif intent['action'] == 'log_activity':
                await self._handle_log_activity(handler, intent['parameters'])
            
            elif intent['action'] == 'bulk_log_activity':
                await self._handle_bulk_log_activity(handler, intent['parameters'])
            
            elif intent['action'] == 'remove_activity':
                await self._handle_remove_activity(handler, intent['parameters'])
            
            elif intent['action'] == 'bulk_remove_activity':
                await self._handle_bulk_remove_activity(handler, intent['parameters'])
            
            elif intent['action'] == 'count_activities':
                await self._handle_count_activities(handler, intent['parameters'])
            
            elif intent['action'] == 'check_points':
                await self._handle_check_points(handler, intent['parameters'])

            elif intent['action'] == 'list_activities':
                await self._handle_list_activities(handler)

            elif intent['action'] == 'list_quotas':
                await self._handle_list_quotas(handler)

            elif intent['action'] in ['check_tenant', 'tenant', 'sector']:
                await self._handle_check_tenant(handler)

            else:
                # Should not happen if unknown is handled
                await handler.send("❌ Unknown action returned from parser.")
        
        except Exception as e:
            print(f"Error executing TF command: {e}")
            try:
                await handler.send(
                    f"❌ An error occurred: {str(e)}"
                )
            except Exception as send_error:
                print(f"Could not send error response: {send_error}")


    
    async def _handle_change_rank(self, handler: ResponseHandler, params: dict):
        """Handle rank change requests"""
        member_name = params.get('member_name')
        new_rank = params.get('new_rank')
        
        if not member_name or not new_rank:
            await handler.send(
                "❌ I need both a member name and a new rank."
            )
            return
        
        # Call API to change rank
        result = await tf_api.change_rank_by_name(
            member_name=member_name,
            new_rank=new_rank,
            reason=f"Promoted via Discord by {handler.user.name}",
            discord_user_id=str(handler.user.id)
        )
        
        if result.get('success'):
            member = result['member']
            roblox_sync = result.get('roblox_sync', {})
            
            embed = discord.Embed(
                title="✅ Rank Updated",
                description=f"Successfully updated **{member['discord_username']}**'s rank",
                color=discord.Color.green()
            )
            embed.add_field(name="Old Rank", value=member['old_rank'], inline=True)
            embed.add_field(name="New Rank", value=member['new_rank'], inline=True)
            embed.add_field(name="Roblox Sync", 
                          value="✅ Success" if roblox_sync.get('success') else "❌ Failed",
                          inline=False)
            embed.set_footer(text=f"Changed by {handler.user.name}")
            
            await handler.send(embed=embed)
        else:
            await handler.send(
                f"❌ Failed to change rank: {result.get('message', 'Unknown error')}"
            )
    
    async def _handle_get_member_info(self, handler: ResponseHandler, params: dict):
        """Handle member info requests"""
        member_name = params.get('member_name')
        
        if not member_name:
            await handler.send("❌ I need a member name.")
            return
        
        # Search for member
        member = await tf_api.find_member_by_name(member_name)
        
        if not member:
            await handler.send(
                f"❌ Could not find member **{member_name}**"
            )
            return
        
        # Get detailed info
        detailed_info = await tf_api.get_member(member['id'])
        
        if detailed_info.get('success'):
            member_data = detailed_info['member']
            
            embed = discord.Embed(
                title=f"📊 Member Info: {member_data['discord_username']}",
                color=discord.Color.blue()
            )
            embed.add_field(name="Discord", value=member_data['discord_username'], inline=True)
            embed.add_field(name="Roblox", value=member_data.get('roblox_username') or 'Not set', inline=True)
            embed.add_field(name="Current Rank", value=member_data['current_rank'], inline=True)
            embed.add_field(name="System join Date", 
                          value=member_data.get('join_date', 'Unknown')[:10] if member_data.get('join_date') else 'Unknown',
                          inline=True)
            
            # Add recent activities
            if member_data.get('recent_activities'):
                activities_text = "\n".join([
                    f"• {a['type']} ({a['points']} pts) - {a['date'][:10] if a.get('date') else 'N/A'}"
                    for a in member_data['recent_activities'][:5]
                ])
                embed.add_field(name="Recent Activities", value=activities_text or "None", inline=False)
            
            await handler.send(embed=embed)
        else:
            await handler.send(
                f"❌ Failed to get member info: {detailed_info.get('message')}"
            )
    
    async def _handle_list_members(self, handler: ResponseHandler, params: dict):
        """Handle list members requests"""
        rank_filter = params.get('rank')
        
        # Get members
        result = await tf_api.get_members(rank=rank_filter)
        
        if result.get('success'):
            members = result['members']
            
            if not members:
                await handler.send(
                    f"No members found" + (f" with rank **{rank_filter}**" if rank_filter else "")
                )
                return
            
            # Create embeds (Discord has limits, so paginate if needed)
            embed = discord.Embed(
                title=f"📋 Members" + (f" - Rank: {rank_filter}" if rank_filter else ""),
                description=f"Total: {len(members)} members",
                color=discord.Color.blue()
            )
            
            # Group by rank
            members_by_rank = {}
            for member in members:
                rank = member['current_rank']
                if rank not in members_by_rank:
                    members_by_rank[rank] = []
                members_by_rank[rank].append(member['discord_username'])
            
            # Add fields for each rank
            for rank, member_list in sorted(members_by_rank.items()):
                members_text = ", ".join(member_list[:10])  # Limit to avoid overflow
                if len(member_list) > 10:
                    members_text += f" ... +{len(member_list) - 10} more"
                embed.add_field(name=f"{rank} ({len(member_list)})", value=members_text, inline=False)
            
            await handler.send(embed=embed)
        else:
            await handler.send(
                f"❌ Failed to get members: {result.get('message')}"
            )
    
    async def _handle_add_member(self, handler: ResponseHandler, params: dict):
        """Handle add member requests"""
        discord_username = params.get('discord_username')
        roblox_username = params.get('roblox_username')
        rank = params.get('rank', 'Aspirant')
        
        if not discord_username:
            await handler.send("❌ I need a Discord username.")
            return
        
        # Add member
        result = await tf_api.add_member(
            discord_username=discord_username,
            roblox_username=roblox_username,
            current_rank=rank,
            discord_user_id=str(handler.user.id)
        )
        
        if result.get('success'):
            member = result['member']
            
            embed = discord.Embed(
                title="✅ Member Added",
                description=f"Successfully added **{member['discord_username']}**",
                color=discord.Color.green()
            )
            embed.add_field(name="Discord", value=member['discord_username'], inline=True)
            embed.add_field(name="Roblox", value=member.get('roblox_username') or 'Not set', inline=True)
            embed.add_field(name="Rank", value=member['current_rank'], inline=True)
            embed.set_footer(text=f"Added by {handler.user.name}")
            
            await handler.send(embed=embed)
        else:
            await handler.send(
                f"❌ Failed to add member: {result.get('message')}"
            )
    
    async def _handle_remove_member(self, handler: ResponseHandler, params: dict):
        """Handle remove member requests"""
        member_name = params.get('member_name')
        
        if not member_name:
            await handler.send("❌ I need a member name.")
            return
        
        # Find member first
        member = await tf_api.find_member_by_name(member_name)
        
        if not member:
            await handler.send(
                f"❌ Could not find member **{member_name}**"
            )
            return
        
        # Remove member
        result = await tf_api.remove_member(
            member_id=member['id'],
            discord_user_id=str(handler.user.id)
        )
        
        if result.get('success'):
            await handler.send(
                f"✅ Successfully removed **{member_name}** from the system."
            )
        else:
            await handler.send(
                f"❌ Failed to remove member: {result.get('message')}"
            )
    
    async def _handle_log_activity(self, handler: ResponseHandler, params: dict):
        """Handle single activity log requests"""
        member_name = params.get('member_name')
        activity_type = params.get('activity_type')
        description = params.get('description')
        # Honour an explicit quantity from Groq even in this handler.
        # Use `or 1` so that Groq returning null/None is treated the same as omitting the field.
        quantity = int(params.get('quantity') or 1)
        
        if not member_name or not activity_type:
            await handler.send(
                "❌ I need both a member name and an activity type."
            )
            return

        if quantity > 200:
            await handler.send(
                f"❌ You can't log more than **200 entries at once** (you requested {quantity}). "
                f"Please split them into smaller batches."
            )
            return
        member = await tf_api.find_member_by_name(member_name)
        
        if not member:
            await handler.send(
                f"❌ Could not find member **{member_name}**"
            )
            return
        
        # Log activity
        try:
            result = await tf_api.log_activity(
                member_id=member['id'],
                activity_type=activity_type,
                description=description or f"{activity_type} logged via Discord",
                discord_user_id=str(handler.user.id),
                quantity=quantity,
            )
            
            if result.get('success'):
                activity = result.get('activity', {})
                points = activity.get('points', 0)
                # Format points (remove .0 if integer)
                points_str = f"{int(points)}" if isinstance(points, (int, float)) and points == int(points) else f"{points}"
                
                # Get quota progress information
                quota_progress = result.get('quota_progress', {})
                total_points = quota_progress.get('total_points', 0)
                quota = quota_progress.get('quota', 0)
                
                total_str = f"{int(total_points)}" if isinstance(total_points, (int, float)) and total_points == int(total_points) else f"{total_points}"
                quota_str = f"{int(quota)}" if isinstance(quota, (int, float)) and quota == int(quota) else f"{quota}"

                qty_str = f" (x{quantity})" if quantity > 1 else ""
                await handler.send(
                    f"✅ Logged {activity_type}{qty_str} ({points_str} pts) for **{member_name}**, "
                    f"they now have {total_str}/{quota_str} points."
                )
            else:
                await handler.send(
                    f"❌ Failed to log activity: {result.get('message', 'Unknown API error')}"
                )
        except Exception as e:
            await handler.send(f"❌ Error processing log response: {str(e)}")
            print(f"Full result: {locals().get('result', 'No result')}")

    async def _handle_bulk_log_activity(self, handler: ResponseHandler, params: dict):
        """Handle bulk activity log requests (quantity > 1)."""
        member_name = params.get('member_name')
        activity_type = params.get('activity_type')
        description = params.get('description')
        quantity = max(1, int(params.get('quantity') or 2))

        if not member_name or not activity_type:
            await handler.send("❌ I need both a member name and an activity type.")
            return

        if quantity > 200:
            await handler.send(
                f"❌ You can't log more than **200 entries at once** (you requested {quantity}). "
                f"Please split them into smaller batches."
            )
            return

        # Find member
        member = await tf_api.find_member_by_name(member_name)
        if not member:
            await handler.send(f"❌ Could not find member **{member_name}**")
            return

        try:
            result = await tf_api.log_activity(
                member_id=member['id'],
                activity_type=activity_type,
                description=description or f"{quantity}x {activity_type} logged via Discord",
                discord_user_id=str(handler.user.id),
                quantity=quantity,
            )

            if result.get('success'):
                activity = result.get('activity', {})
                total_pts = activity.get('points', 0)
                points_str = f"{int(total_pts)}" if isinstance(total_pts, (int, float)) and total_pts == int(total_pts) else f"{total_pts}"

                quota_progress = result.get('quota_progress', {})
                total_points = quota_progress.get('total_points', 0)
                quota = quota_progress.get('quota', 0)
                total_str = f"{int(total_points)}" if isinstance(total_points, (int, float)) and total_points == int(total_points) else f"{total_points}"
                quota_str = f"{int(quota)}" if isinstance(quota, (int, float)) and quota == int(quota) else f"{quota}"

                await handler.send(
                    f"✅ Logged **{quantity}x {activity_type}** ({points_str} pts total) for **{member_name}**, "
                    f"they now have {total_str}/{quota_str} points."
                )
            else:
                await handler.send(
                    f"❌ Failed to log activities: {result.get('message', 'Unknown API error')}"
                )
        except Exception as e:
            await handler.send(f"❌ Error logging activities: {str(e)}")
            print(f"Full result: {locals().get('result', 'No result')}")

    async def _handle_remove_activity(self, handler: ResponseHandler, params: dict):
        """Handle single activity removal — delegates to the by-type API endpoint."""
        member_name = params.get('member_name')
        activity_type = params.get('activity_type')

        if not member_name:
            await handler.send("❌ I need a member name to find which activity to remove.")
            return

        member = await tf_api.find_member_by_name(member_name)
        if not member:
            await handler.send(f"❌ Could not find member **{member_name}**")
            return

        # If no activity type, fall back to removing the single most-recent entry
        # by fetching the latest activity and passing its type.
        if not activity_type:
            activities_result = await tf_api.get_member_activities(member['id'], limit=1)
            activities = activities_result.get('activities', [])
            if not activities:
                await handler.send(f"❌ No activities found for **{member_name}**")
                return
            activity_type = activities[0]['activity_type']

        try:
            result = await tf_api.remove_activities_by_type(
                member_id=member['id'],
                activity_type=activity_type,
                quantity=1,
                discord_user_id=str(handler.user.id),
            )

            if result.get('success'):
                quota_progress = result.get('quota_progress', {})
                total_points = quota_progress.get('total_points', 0)
                quota = quota_progress.get('quota', 0)
                total_str = f"{int(total_points)}" if isinstance(total_points, (int, float)) and total_points == int(total_points) else f"{total_points}"
                quota_str = f"{int(quota)}" if isinstance(quota, (int, float)) and quota == int(quota) else f"{quota}"

                await handler.send(
                    f"✅ Removed **{activity_type}** from **{member_name}**, "
                    f"they now have {total_str}/{quota_str} points."
                )
            else:
                await handler.send(
                    f"❌ Failed to remove activity: {result.get('message', 'Unknown API error')}"
                )
        except Exception as e:
            await handler.send(f"❌ Error removing activity: {str(e)}")
            print(f"Full result: {locals().get('result', 'No result')}")

    async def _handle_bulk_remove_activity(self, handler: ResponseHandler, params: dict):
        """Handle bulk activity removal (quantity > 1)."""
        member_name = params.get('member_name')
        activity_type = params.get('activity_type')
        quantity = max(1, int(params.get('quantity') or 2))

        if not member_name:
            await handler.send("❌ I need a member name.")
            return
        if not activity_type:
            await handler.send("❌ I need an activity type to remove in bulk.")
            return

        member = await tf_api.find_member_by_name(member_name)
        if not member:
            await handler.send(f"❌ Could not find member **{member_name}**")
            return

        try:
            result = await tf_api.remove_activities_by_type(
                member_id=member['id'],
                activity_type=activity_type,
                quantity=quantity,
                discord_user_id=str(handler.user.id),
            )

            if result.get('success'):
                deleted = result.get('deleted', quantity)
                quota_progress = result.get('quota_progress', {})
                total_points = quota_progress.get('total_points', 0)
                quota = quota_progress.get('quota', 0)
                total_str = f"{int(total_points)}" if isinstance(total_points, (int, float)) and total_points == int(total_points) else f"{total_points}"
                quota_str = f"{int(quota)}" if isinstance(quota, (int, float)) and quota == int(quota) else f"{quota}"

                await handler.send(
                    f"✅ Removed **{deleted}x {activity_type}** from **{member_name}**, "
                    f"they now have {total_str}/{quota_str} points."
                )
            else:
                await handler.send(
                    f"❌ Failed to remove activities: {result.get('message', 'Unknown API error')}"
                )
        except Exception as e:
            await handler.send(f"❌ Error removing activities: {str(e)}")
            print(f"Full result: {locals().get('result', 'No result')}")

    async def _handle_count_activities(self, handler: ResponseHandler, params: dict):
        """Handle count activities by type requests."""
        member_name = params.get('member_name')
        activity_type = params.get('activity_type')  # None = show all types
        period_only = bool(params.get('period_only', False))

        if not member_name:
            await handler.send("❌ I need a member name to count activities.")
            return

        member = await tf_api.find_member_by_name(member_name)
        if not member:
            await handler.send(f"❌ Could not find member **{member_name}**")
            return

        try:
            result = await tf_api.count_activities_by_type(
                member_id=member['id'],
                activity_type=activity_type,
                period_only=period_only,
            )

            if result.get('success'):
                count = result.get('count', 0)
                breakdown = result.get('breakdown', {})
                period_label = " (this period)" if period_only else ""

                if activity_type:
                    # Single-type response
                    await handler.send(
                        f"📊 **{member_name}** has **{count}** {activity_type} "
                        f"entr{'y' if count == 1 else 'ies'}{period_label}."
                    )
                else:
                    # Full breakdown embed
                    embed = discord.Embed(
                        title=f"📊 Activity Count: {member_name}{period_label}",
                        description=f"**Total: {count} entries**",
                        color=discord.Color.blue(),
                    )
                    for atype, cnt in sorted(breakdown.items(), key=lambda x: -x[1]):
                        embed.add_field(name=atype, value=str(cnt), inline=True)
                    if not breakdown:
                        embed.description = "No activities found."
                    await handler.send(embed=embed)
            else:
                await handler.send(
                    f"❌ Failed to count activities: {result.get('message', 'Unknown error')}"
                )
        except Exception as e:
            await handler.send(f"❌ Error counting activities: {str(e)}")


    async def _handle_check_points(self, handler: ResponseHandler, params: dict):
        """Handle check points requests"""
        member_name = params.get('member_name')
        
        # If no member name specified, we can't check points (would need Discord ID mapping)
        if not member_name:
            await handler.send(
                "❌ I need a member name to check points. (Note: Checking your own points requires staff implementation)"
            )
            return
        
        # Find member
        member = await tf_api.find_member_by_name(member_name)
        
        if not member:
            await handler.send(
                f"❌ Could not find member **{member_name}**"
            )
            return
        
        # Get member's current points
        try:
            result = await tf_api.get_member_points(member['id'])
            
            if result.get('success'):
                points_data = result.get('points', {})
                total_points = points_data.get('total_points', 0)
                quota = points_data.get('quota', 0)
                percentage = points_data.get('percentage', 0)
                
                # Format points (remove .0 if integer)
                total_str = f"{int(total_points)}" if isinstance(total_points, (int, float)) and total_points == int(total_points) else f"{total_points}"
                quota_str = f"{int(quota)}" if isinstance(quota, (int, float)) and quota == int(quota) else f"{quota}"
                
                # Create embed for visual display
                embed = discord.Embed(
                    title=f"📊 AC Points: {member_name}",
                    color=discord.Color.blue()
                )
                embed.add_field(name="Current Points", value=total_str, inline=True)
                embed.add_field(name="Quota Required", value=quota_str, inline=True)
                embed.add_field(name="Progress", value=f"{percentage}%", inline=True)
                
                # Add status bar
                if quota > 0:
                    progress_value = min(int(percentage / 10), 10)
                    bar = "█" * progress_value + "░" * (10 - progress_value)
                    embed.add_field(name="Status", value=bar, inline=False)
                    
                    if percentage >= 100:
                        embed.add_field(name="", value="✅ Quota complete!", inline=False)
                    else:
                        points_needed = quota - total_points
                        embed.add_field(name="", value=f"⏳ {points_needed} more points needed", inline=False)
                
                await handler.send(embed=embed)
            else:
                await handler.send(
                    f"❌ Could not retrieve points: {result.get('message', 'Unknown error')}"
                )
        except Exception as e:
            await handler.send(f"❌ Error checking points: {str(e)}")

    async def _handle_list_activities(self, handler: ResponseHandler):
        """Display all currently configured active activity types and their point values."""
        try:
            activities = await tf_api.get_activity_types(force_refresh=True)
            if not activities:
                await handler.send("❌ Could not retrieve activity types from the system.")
                return

            embed = discord.Embed(
                title="📋 Taskforce Activity Point Values",
                description="Current point values and cycle limits configured in the system:",
                color=discord.Color.purple()
            )
            for act in activities:
                name = act.get('name', 'Unknown')
                pts = act.get('points', 0.0)
                pts_str = f"{int(pts)}" if pts == int(pts) else f"{pts}"
                limit_info = "⚠️ *Max 1 per cycle*" if act.get('is_limited') else "✅ *Unlimited*"
                desc = f"\n> {act.get('description')}" if act.get('description') else ""
                embed.add_field(
                    name=f"{name} — {pts_str} pts",
                    value=f"{limit_info}{desc}",
                    inline=False
                )
            await handler.send(embed=embed)
        except Exception as e:
            await handler.send(f"❌ Error listing activities: {e}")

    async def _handle_list_quotas(self, handler: ResponseHandler):
        """Display all currently configured rank quota requirements."""
        try:
            quotas = await tf_api.get_rank_quotas(force_refresh=True)
            if not quotas:
                await handler.send("❌ Could not retrieve rank quotas from the system.")
                return

            embed = discord.Embed(
                title="🎖️ Rank Quota Requirements",
                description="Current AC quota point requirements by rank:",
                color=discord.Color.gold()
            )
            for q in quotas:
                rank_name = q.get('rank_name', 'Unknown')
                pts = q.get('required_points', 0.0)
                pts_str = f"{int(pts)}" if pts == int(pts) else f"{pts}"
                embed.add_field(
                    name=rank_name,
                    value=f"**{pts_str}** points required",
                    inline=True
                )
            await handler.send(embed=embed)
        except Exception as e:
            await handler.send(f"❌ Error listing quotas: {e}")

# Setup function for adding the cog to your bot
async def setup(bot):
    await bot.add_cog(TFSystemCog(bot))


# Example: Add this to your main bot file
"""
# In your main bot.py file:

import discord
from discord.ext import commands
import os
from dotenv import load_dotenv

load_dotenv()

# Create bot
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f'Bot is ready! Logged in as {bot.user}')
    # Sync commands
    await bot.tree.sync()

# Load TF System cog
async def main():
    async with bot:
        await bot.load_extension('tf_commands')  # Load this file
        await bot.start(os.getenv('DISCORD_TOKEN'))

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
"""
