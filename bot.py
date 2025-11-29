# Discord Manager Bot - Auto-Deployed via GitHub Actions
import discord
from discord import app_commands
from discord.ext import commands
import json
import os
from dotenv import load_dotenv
from typing import Literal, Optional
import logging
from datetime import datetime
from main import DiscordPermissionScheduler
import pytz

# Load environment variables
load_dotenv()

# Logging setup - All logs saved to files
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

# Create logger
logger = logging.getLogger(__name__)

class ConfigManager:
    """Manages the config.json file operations"""
    
    def __init__(self, config_file='config.json'):
        self.config_file = config_file
        logger.info(f"[INIT] ConfigManager initialized with {config_file}")
    
    def load_config(self) -> dict:
        """Load the current configuration"""
        try:
            with open(self.config_file, 'r') as f:
                config = json.load(f)
                logger.info(f"[OK] Configuration loaded successfully from {self.config_file}")
                return config
        except FileNotFoundError:
            logger.warning(f"[WARNING] Config file {self.config_file} not found, creating empty config")
            return {"tasks": {}}
        except json.JSONDecodeError:
            logger.error(f"[ERROR] Invalid JSON in {self.config_file}")
            return {"tasks": {}}
    
    def save_config(self, config: dict) -> bool:
        """Save configuration to file"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
                logger.info(f"[OK] Configuration saved successfully to {self.config_file}")
            return True
        except Exception as e:
            logger.error(f"[ERROR] Failed to save config: {e}")
            return False
    
    def add_task(self, task_name: str, task_data: dict) -> tuple[bool, str]:
        """Add a new task"""
        logger.info(f"[ACTION] Attempting to add task: {task_name}")
        config = self.load_config()
        
        if task_name in config.get('tasks', {}):
            logger.warning(f"[WARNING] Task '{task_name}' already exists")
            return False, f"Task '{task_name}' already exists!"
        
        if 'tasks' not in config:
            config['tasks'] = {}
        
        config['tasks'][task_name] = task_data
        
        if self.save_config(config):
            logger.info(f"[SUCCESS] Task '{task_name}' added successfully")
            return True, f"Task '{task_name}' added successfully!"
        
        logger.error(f"[ERROR] Failed to save configuration for task '{task_name}'")
        return False, "Failed to save configuration!"
    
    def remove_task(self, task_name: str) -> tuple[bool, str]:
        """Remove a task"""
        logger.info(f"[ACTION] Attempting to remove task: {task_name}")
        config = self.load_config()
        
        if task_name not in config.get('tasks', {}):
            logger.warning(f"[WARNING] Task '{task_name}' not found")
            return False, f"Task '{task_name}' not found!"
        
        del config['tasks'][task_name]
        
        if self.save_config(config):
            logger.info(f"[SUCCESS] Task '{task_name}' removed successfully")
            return True, f"Task '{task_name}' removed successfully!"
        
        logger.error(f"[ERROR] Failed to remove task '{task_name}'")
        return False, "Failed to save configuration!"
    
    def update_task(self, task_name: str, task_data: dict) -> tuple[bool, str]:
        """Update an existing task"""
        logger.info(f"[ACTION] Attempting to update task: {task_name}")
        config = self.load_config()
        
        if task_name not in config.get('tasks', {}):
            logger.warning(f"[WARNING] Task '{task_name}' not found for update")
            return False, f"Task '{task_name}' not found!"
        
        config['tasks'][task_name] = task_data
        
        if self.save_config(config):
            logger.info(f"[SUCCESS] Task '{task_name}' updated successfully")
            return True, f"Task '{task_name}' updated successfully!"
        
        logger.error(f"[ERROR] Failed to update task '{task_name}'")
        return False, "Failed to save configuration!"
    
    def get_task(self, task_name: str) -> Optional[dict]:
        """Get a specific task"""
        logger.debug(f"[DEBUG] Retrieving task: {task_name}")
        config = self.load_config()
        return config.get('tasks', {}).get(task_name)
    
    def list_tasks(self) -> dict:
        """List all tasks"""
        logger.debug(f"[DEBUG] Listing all tasks")
        config = self.load_config()
        return config.get('tasks', {})
    
        # NEW METHODS FOR MESSAGES
    def get_opening_message(self) -> str:
        """Get the opening message"""
        logger.debug(f"[DEBUG] Retrieving opening message")
        config = self.load_config()
        return config.get('opening_message', '')
    
    def get_closing_message(self) -> str:
        """Get the closing message"""
        logger.debug(f"[DEBUG] Retrieving closing message")
        config = self.load_config()
        return config.get('closing_message', '')
    
    def set_opening_message(self, message: str) -> tuple[bool, str]:
        """Set the opening message"""
        logger.info(f"[ACTION] Setting opening message: {message}")
        config = self.load_config()
        config['opening_message'] = message
        
        if self.save_config(config):
            logger.info(f"[SUCCESS] Opening message set successfully")
            return True, "Opening message set successfully!"
        
        logger.error(f"[ERROR] Failed to save opening message")
        return False, "Failed to save configuration!"
    
    def set_closing_message(self, message: str) -> tuple[bool, str]:
        """Set the closing message"""
        logger.info(f"[ACTION] Setting closing message: {message}")
        config = self.load_config()
        config['closing_message'] = message
        
        if self.save_config(config):
            logger.info(f"[SUCCESS] Closing message set successfully")
            return True, "Closing message set successfully!"
        
        logger.error(f"[ERROR] Failed to save closing message")
        return False, "Failed to save configuration!"
    
    def get_messages(self) -> dict:
        """Get both opening and closing messages"""
        logger.debug(f"[DEBUG] Retrieving all messages")
        config = self.load_config()
        return {
            'opening_message': config.get('opening_message', ''),
            'closing_message': config.get('closing_message', '')
        }


class SchedulerBot(commands.Bot):
    def __init__(self):
        # Intents required for the bot
        intents = discord.Intents.all()
        
        # Initialize without prefix - slash commands only
        super().__init__(command_prefix="ThisBotDoesNotUsePrefixCommands_", intents=intents, help_command=None)
        self.config_manager = ConfigManager()
        logger.info("[INIT] SchedulerBot initialized")
        
    async def setup_hook(self):
        """Setup hook for slash commands"""
        # Sync commands globally
        await self.tree.sync()
        logger.info("[OK] Slash commands synced globally")


# Initialize bot
bot = SchedulerBot()


# Admin check decorator
def is_admin():
    """Check if user is authorized to use bot commands"""
    async def predicate(interaction: discord.Interaction) -> bool:
        # Get admin user IDs from environment variable
        admin_ids = os.getenv('ADMIN_IDS', '').split(',')
        admin_ids = [int(id.strip()) for id in admin_ids if id.strip().isdigit()]
        
        if interaction.user.id in admin_ids:
            logger.info(f"[AUTH] User {interaction.user.name} ({interaction.user.id}) authorized as admin")
            return True
        
        # Also check for administrator permission
        if isinstance(interaction.user, discord.Member):
            if interaction.user.guild_permissions.administrator:
                logger.info(f"[AUTH] User {interaction.user.name} ({interaction.user.id}) authorized via Administrator permission")
                return True
        
        logger.warning(f"[AUTH] Unauthorized access attempt by {interaction.user.name} ({interaction.user.id})")
        await interaction.response.send_message(
            "[ERROR] You don't have permission to use this command!",
            ephemeral=True
        )
        return False
    
    return app_commands.check(predicate)


@bot.event
async def on_ready():
    """Called when bot is ready"""
    logger.info("=" * 60)
    logger.info(f'[OK] Bot logged in as {bot.user}')
    logger.info(f'[OK] Bot ID: {bot.user.id}')
    logger.info(f'[OK] Connected to {len(bot.guilds)} server(s)')
    
    for guild in bot.guilds:
        logger.info(f'[INFO] Connected to guild: {guild.name} (ID: {guild.id})')
    
    logger.info("=" * 60)
    
    # Set bot status
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="scheduled tasks | /help"
        )
    )
    logger.info("[OK] Bot status set")


# ===========================
# SLASH COMMANDS
# ===========================

@bot.tree.command(name="tasks", description="List all scheduled tasks")
@is_admin()
async def list_tasks(interaction: discord.Interaction):
    """List all tasks"""
    logger.info(f"[COMMAND] /tasks executed by {interaction.user.name}")
    tasks = bot.config_manager.list_tasks()
    
    if not tasks:
        embed = discord.Embed(
            title="[INFO] Scheduled Tasks",
            description="No tasks configured!",
            color=discord.Color.orange()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        logger.info(f"[INFO] No tasks to display")
        return
    
    embed = discord.Embed(
        title="[INFO] Scheduled Tasks",
        description=f"Total Tasks: **{len(tasks)}**",
        color=discord.Color.blue(),
        timestamp=datetime.utcnow()
    )
    
    for task_name, task_data in tasks.items():
        action = task_data.get('action', 'custom')
        time = task_data.get('lock_time', 'N/A')
        channel_id = task_data.get('channel_id', 'N/A')
        
        action_label = {
            'lock': '[LOCK]',
            'unlock': '[UNLOCK]',
            'custom': '[CUSTOM]'
        }.get(action, '[TASK]')
        
        embed.add_field(
            name=f"{action_label} **{task_name}**",
            value=f"Action: `{action}`\nTime: `{time}`\nChannel: `{channel_id}`",
            inline=False
        )
    
    embed.set_footer(text="Use /task-info <name> for detailed information")
    await interaction.response.send_message(embed=embed, ephemeral=True)
    logger.info(f"[INFO] Displayed {len(tasks)} tasks")


@bot.tree.command(name="task-info", description="Get detailed information about a task")
@app_commands.describe(task_name="Name of the task")
@is_admin()
async def task_info(interaction: discord.Interaction, task_name: str):
    """Get task details"""
    logger.info(f"[COMMAND] /task-info executed by {interaction.user.name} for task: {task_name}")
    task = bot.config_manager.get_task(task_name)
    
    if not task:
        embed = discord.Embed(
            title="[ERROR] Task Not Found",
            description=f"Task '{task_name}' does not exist!",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        logger.warning(f"[WARNING] Task '{task_name}' not found")
        return
    
    action = task.get('action', 'custom')
    action_label = {
        'lock': '[LOCK]',
        'unlock': '[UNLOCK]',
        'custom': '[CUSTOM]'
    }.get(action, '[TASK]')
    
    embed = discord.Embed(
        title=f"{action_label} Task: {task_name}",
        color=discord.Color.green(),
        timestamp=datetime.utcnow()
    )
    
    # Format the task data nicely
    task_json = json.dumps(task, indent=2)
    
    embed.add_field(
        name="Configuration",
        value=f"```json\n{task_json}\n```",
        inline=False
    )
    
    embed.set_footer(text="This configuration will be synced to the scheduler")
    await interaction.response.send_message(embed=embed, ephemeral=True)
    logger.info(f"[INFO] Displayed info for task: {task_name}")


@bot.tree.command(name="add-lock-task", description="Add a new channel lock task")
@app_commands.describe(
    task_name="Unique name for this task",
    time="Time to execute (e.g., 'Monday 10:30pm' or '14:30')",
    channel_id="Discord channel ID",
    guild_id="Discord server/guild ID",
    reason="Reason for the lock"
)
@is_admin()
async def add_lock_task(
    interaction: discord.Interaction,
    task_name: str,
    time: str,
    channel_id: str,
    guild_id: str,
    reason: str = "Scheduled lock"
):
    """Add a lock task"""
    logger.info(f"[COMMAND] /add-lock-task executed by {interaction.user.name}")
    logger.info(f"[INFO] Task Name: {task_name}, Time: {time}, Channel: {channel_id}")
    
    task_data = {
        "action": "lock",
        "lock_time": time,
        "channel_id": channel_id,
        "guild_id": guild_id,
        "reason": reason
    }
    
    success, message = bot.config_manager.add_task(task_name, task_data)
    
    if success:
        embed = discord.Embed(
            title="[SUCCESS] Task Added Successfully",
            description=message,
            color=discord.Color.green()
        )
        embed.add_field(
            name="Task Details",
            value=f"```json\n{json.dumps(task_data, indent=2)}\n```",
            inline=False
        )
        embed.set_footer(text="Scheduler will detect this task within 5 minutes")
        logger.info(f"[SUCCESS] Lock task '{task_name}' added successfully")
    else:
        embed = discord.Embed(
            title="[ERROR]",
            description=message,
            color=discord.Color.red()
        )
        logger.error(f"[ERROR] Failed to add lock task '{task_name}': {message}")
    
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="add-unlock-task", description="Add a new channel unlock task")
@app_commands.describe(
    task_name="Unique name for this task",
    time="Time to execute (e.g., 'Monday 10:30pm' or '14:30')",
    channel_id="Discord channel ID",
    guild_id="Discord server/guild ID",
    reason="Reason for the unlock"
)
@is_admin()
async def add_unlock_task(
    interaction: discord.Interaction,
    task_name: str,
    time: str,
    channel_id: str,
    guild_id: str,
    reason: str = "Scheduled unlock"
):
    """Add an unlock task"""
    logger.info(f"[COMMAND] /add-unlock-task executed by {interaction.user.name}")
    logger.info(f"[INFO] Task Name: {task_name}, Time: {time}, Channel: {channel_id}")
    
    task_data = {
        "action": "unlock",
        "lock_time": time,
        "channel_id": channel_id,
        "guild_id": guild_id,
        "reason": reason
    }
    
    success, message = bot.config_manager.add_task(task_name, task_data)
    
    if success:
        embed = discord.Embed(
            title="[SUCCESS] Task Added Successfully",
            description=message,
            color=discord.Color.green()
        )
        embed.add_field(
            name="Task Details",
            value=f"```json\n{json.dumps(task_data, indent=2)}\n```",
            inline=False
        )
        embed.set_footer(text="Scheduler will detect this task within 5 minutes")
        logger.info(f"[SUCCESS] Unlock task '{task_name}' added successfully")
    else:
        embed = discord.Embed(
            title="[ERROR]",
            description=message,
            color=discord.Color.red()
        )
        logger.error(f"[ERROR] Failed to add unlock task '{task_name}': {message}")
    
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="remove-task", description="Remove a scheduled task")
@app_commands.describe(task_name="Name of the task to remove")
@is_admin()
async def remove_task(interaction: discord.Interaction, task_name: str):
    """Remove a task"""
    logger.info(f"[COMMAND] /remove-task executed by {interaction.user.name} for task: {task_name}")
    success, message = bot.config_manager.remove_task(task_name)
    
    if success:
        embed = discord.Embed(
            title="[SUCCESS] Task Removed",
            description=message,
            color=discord.Color.green()
        )
        logger.info(f"[SUCCESS] Task '{task_name}' removed successfully")
    else:
        embed = discord.Embed(
            title="[ERROR]",
            description=message,
            color=discord.Color.red()
        )
        logger.error(f"[ERROR] Failed to remove task '{task_name}': {message}")
    
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="update-task-time", description="Update the execution time of a task")
@app_commands.describe(
    task_name="Name of the task",
    new_time="New time (e.g., 'Monday 10:30pm' or '14:30')"
)
@is_admin()
async def update_task_time(interaction: discord.Interaction, task_name: str, new_time: str):
    """Update task time"""
    logger.info(f"[COMMAND] /update-task-time executed by {interaction.user.name}")
    logger.info(f"[INFO] Task: {task_name}, New Time: {new_time}")
    
    task = bot.config_manager.get_task(task_name)
    
    if not task:
        embed = discord.Embed(
            title="[ERROR] Task Not Found",
            description=f"Task '{task_name}' does not exist!",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        logger.warning(f"[WARNING] Task '{task_name}' not found for time update")
        return
    
    old_time = task.get('lock_time', 'N/A')
    task['lock_time'] = new_time
    success, message = bot.config_manager.update_task(task_name, task)
    
    if success:
        embed = discord.Embed(
            title="[SUCCESS] Task Updated",
            description=f"Task '{task_name}' time has been updated!",
            color=discord.Color.green()
        )
        embed.add_field(name="Old Time", value=f"`{old_time}`", inline=True)
        embed.add_field(name="New Time", value=f"`{new_time}`", inline=True)
        logger.info(f"[SUCCESS] Task '{task_name}' time updated from '{old_time}' to '{new_time}'")
    else:
        embed = discord.Embed(
            title="[ERROR]",
            description=message,
            color=discord.Color.red()
        )
        logger.error(f"[ERROR] Failed to update task '{task_name}' time: {message}")
    
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="clear-all-tasks", description="Remove ALL tasks (use with caution!)")
@is_admin()
async def clear_all_tasks(interaction: discord.Interaction):
    """Clear all tasks"""
    logger.info(f"[COMMAND] /clear-all-tasks executed by {interaction.user.name}")
    tasks_count = len(bot.config_manager.list_tasks())
    
    if tasks_count == 0:
        embed = discord.Embed(
            title="[INFO] No Tasks",
            description="There are no tasks to clear!",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        logger.info(f"[INFO] No tasks to clear")
        return
    
    config = {"tasks": {}}
    
    if bot.config_manager.save_config(config):
        embed = discord.Embed(
            title="[SUCCESS] All Tasks Cleared",
            description=f"Successfully removed **{tasks_count}** task(s)!",
            color=discord.Color.orange()
        )
        logger.warning(f"[WARNING] All tasks cleared ({tasks_count} tasks removed) by {interaction.user.name}")
    else:
        embed = discord.Embed(
            title="[ERROR]",
            description="Failed to clear tasks!",
            color=discord.Color.red()
        )
        logger.error(f"[ERROR] Failed to clear all tasks")
    
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="export-config", description="Export current configuration")
@is_admin()
async def export_config(interaction: discord.Interaction):
    """Export config as JSON"""
    logger.info(f"[COMMAND] /export-config executed by {interaction.user.name}")
    config = bot.config_manager.load_config()
    config_json = json.dumps(config, indent=2)
    
    # Create a file-like object
    import io
    file = io.BytesIO(config_json.encode('utf-8'))
    file.seek(0)
    
    embed = discord.Embed(
        title="[EXPORT] Configuration Export",
        description="Current configuration file attached below",
        color=discord.Color.blue(),
        timestamp=datetime.utcnow()
    )
    
    await interaction.response.send_message(
        embed=embed,
        file=discord.File(file, filename='config.json'),
        ephemeral=True
    )
    logger.info(f"[INFO] Configuration exported by {interaction.user.name}")

# ===========================
# MESSAGE CONFIGURATION COMMANDS
# ===========================

@bot.tree.command(name="set-opening-message", description="Set the default opening message for unlock actions")
@app_commands.describe(message="Message to send when unlocking channels (leave empty to use default)")
@is_admin()
async def set_opening_message(interaction: discord.Interaction, message: str = ""):
    """Set opening message"""
    logger.info(f"[COMMAND] /set-opening-message executed by {interaction.user.name}")
    logger.info(f"[INFO] New opening message: {message}")
    
    success, result_message = bot.config_manager.set_opening_message(message)
    
    if success:
        embed = discord.Embed(
            title="Opening Message Updated",
            color=discord.Color.green(),
            timestamp=datetime.utcnow()
        )
        
        if message:
            embed.add_field(
                name="New Opening Message",
                value=f"```{message}```",
                inline=False
            )
        else:
            embed.add_field(
                name="Opening Message",
                value="*Set to empty (will use scheduler's default)*",
                inline=False
            )
        
        embed.set_footer(text="This message will be used for all unlock tasks without custom messages")
        logger.info(f"[SUCCESS] Opening message updated successfully")
    else:
        embed = discord.Embed(
            title="ERROR",
            description=result_message,
            color=discord.Color.red()
        )
        logger.error(f"[ERROR] Failed to set opening message: {result_message}")
    
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="set-closing-message", description="Set the default closing message for lock actions")
@app_commands.describe(message="Message to send when locking channels (leave empty to use default)")
@is_admin()
async def set_closing_message(interaction: discord.Interaction, message: str = ""):
    """Set closing message"""
    logger.info(f"[COMMAND] /set-closing-message executed by {interaction.user.name}")
    logger.info(f"[INFO] New closing message: {message}")
    
    success, result_message = bot.config_manager.set_closing_message(message)
    
    if success:
        embed = discord.Embed(
            title="Closing Message Updated",
            color=discord.Color.green(),
            timestamp=datetime.utcnow()
        )
        
        if message:
            embed.add_field(
                name="New Closing Message",
                value=f"```{message}```",
                inline=False
            )
        else:
            embed.add_field(
                name="Closing Message",
                value="*Set to empty (will use scheduler's default)*",
                inline=False
            )
        
        embed.set_footer(text="This message will be used for all lock tasks without custom messages")
        logger.info(f"[SUCCESS] Closing message updated successfully")
    else:
        embed = discord.Embed(
            title="ERROR",
            description=result_message,
            color=discord.Color.red()
        )
        logger.error(f"[ERROR] Failed to set closing message: {result_message}")
    
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="view-messages", description="View current opening and closing messages")
@is_admin()
async def view_messages(interaction: discord.Interaction):
    """View current messages"""
    logger.info(f"[COMMAND] /view-messages executed by {interaction.user.name}")
    
    messages = bot.config_manager.get_messages()
    opening = messages.get('opening_message', '')
    closing = messages.get('closing_message', '')
    
    embed = discord.Embed(
        title="Default Messages",
        description="Current opening and closing messages for tasks",
        color=discord.Color.blue(),
        timestamp=datetime.utcnow()
    )
    
    # Opening Message
    if opening:
        embed.add_field(
            name="Opening Message (Unlock)",
            value=f"```{opening}```",
            inline=False
        )
    else:
        embed.add_field(
            name="Opening Message (Unlock)",
            value="*Not set - using scheduler default*\n`Channel has been unlocked.`",
            inline=False
        )
    
    # Closing Message
    if closing:
        embed.add_field(
            name="Closing Message (Lock)",
            value=f"```{closing}```",
            inline=False
        )
    else:
        embed.add_field(
            name=" Message (Lock)",
            value="*Not set - using scheduler default*\n`Channel has been locked.`",
            inline=False
        )
    
    embed.set_footer(text="Use /set-opening-message and /set-closing-message to change")
    
    await interaction.response.send_message(embed=embed, ephemeral=True)
    logger.info(f"[INFO] Messages displayed to {interaction.user.name}")

# ===========================
# AUTO-CASH MANAGEMENT COMMANDS
# ===========================

# ===========================
# AUTO-CASH MANAGEMENT COMMANDS
# ===========================

@bot.tree.command(name="autocash-view", description="View current auto-cash configuration")
@is_admin()
async def autocash_view(interaction: discord.Interaction):
    """View auto-cash configuration"""
    logger.info(f"[COMMAND] /autocash-view executed by {interaction.user.name}")
    
    config = bot.config_manager.load_config()
    auto_cash = config.get('auto_cash', {})
    
    # Check if auto-cash exists
    if not auto_cash:
        embed = discord.Embed(
            title="[INFO] Auto-Cash Not Configured",
            description="Auto-cash has not been set up yet!",
            color=discord.Color.orange()
        )
        embed.add_field(
            name="Get Started",
            value=(
                "Use `/autocash-config` to configure auto-cash settings\n"
                "Example: `/autocash-config time: 12:00 AM channel_id: 123456789`"
            ),
            inline=False
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    # Get status
    enabled = auto_cash.get('enabled', False)
    status_emoji = "[ENABLED]" if enabled else "[DISABLED]"
    status_color = discord.Color.green() if enabled else discord.Color.red()
    
    embed = discord.Embed(
        title=f"{status_emoji} Auto-Cash Configuration",
        description=f"Current auto-cash settings and status",
        color=status_color,
        timestamp=datetime.utcnow()
    )
    
    # Status
    embed.add_field(
        name="Status",
        value=f"**{'Enabled' if enabled else 'Disabled'}**",
        inline=True
    )
    
    # Execution Time
    time_value = auto_cash.get('time', 'Not set')
    embed.add_field(
        name="Execution Time",
        value=f"`{time_value}`",
        inline=True
    )
    
    # Channel
    channel_id = auto_cash.get('channel_id', 'Not set')
    if channel_id != 'Not set':
        embed.add_field(
            name="Channel",
            value=f"<#{channel_id}>\n`{channel_id}`",
            inline=True
        )
    else:
        embed.add_field(
            name="Channel",
            value="`Not set`",
            inline=True
        )
    
    # Command Template
    template = auto_cash.get('command_template', 'Not set')
    embed.add_field(
        name="Command Template",
        value=f"`{template}`",
        inline=False
    )
    
    # Check if {amount} is in template
    if template != 'Not set' and '{amount}' not in template:
        embed.add_field(
            name="[WARNING] Template Issue",
            value="Template is missing `{amount}` placeholder!",
            inline=False
        )
    
    # Weekday Amounts
    amounts = auto_cash.get('amounts', {})
    if amounts:
        amounts_text = ""
        for day in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']:
            amount = amounts.get(day, 'Not set')
            amounts_text += f"**{day}:** `{amount}`\n"
        
        embed.add_field(
            name="Weekday Amounts",
            value=amounts_text,
            inline=False
        )
    else:
        embed.add_field(
            name="Weekday Amounts",
            value="*No amounts configured*",
            inline=False
        )
    
    # Preview command for today
    ist_tz = pytz.timezone('Asia/Kolkata')
    current_time = datetime.now(ist_tz)
    weekdays = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    today = weekdays[current_time.weekday()]
    today_amount = amounts.get(today, 'Not set')
    
    if today_amount != 'Not set' and template != 'Not set':
        preview_command = template.format(amount=today_amount)
        embed.add_field(
            name=f"Preview (Today - {today})",
            value=f"`{preview_command}`",
            inline=False
        )
    
    # Configuration completeness check
    issues = []
    if not enabled:
        issues.append("Auto-cash is disabled")
    if channel_id == 'Not set':
        issues.append("Channel ID not set")
    if time_value == 'Not set':
        issues.append("Execution time not set")
    if template == 'Not set':
        issues.append("Command template not set")
    if not amounts or len(amounts) < 7:
        issues.append("Not all weekday amounts are configured")
    
    if issues:
        embed.add_field(
            name="[INFO] Configuration Status",
            value="\n".join([f"• {issue}" for issue in issues]),
            inline=False
        )
    else:
        embed.add_field(
            name="[OK] Configuration Status",
            value="All settings configured correctly!",
            inline=False
        )
    
    embed.set_footer(text="Use /autocash-config to modify settings | /autocash-enable or /autocash-disable to toggle")
    
    await interaction.response.send_message(embed=embed, ephemeral=True)
    logger.info(f"[INFO] Auto-cash config displayed to {interaction.user.name}")


@bot.tree.command(name="autocash-enable", description="Enable auto-cash feature")
@is_admin()
async def autocash_enable(interaction: discord.Interaction):
    """Enable auto-cash"""
    logger.info(f"[COMMAND] /autocash-enable executed by {interaction.user.name}")
    
    config = bot.config_manager.load_config()
    
    # Ensure auto_cash section exists
    if 'auto_cash' not in config:
        config['auto_cash'] = {
            'enabled': False,
            'time': '12:00 AM',
            'channel_id': '',
            'command_template': '$add-cash {amount}',
            'amounts': {}
        }
    
    auto_cash = config['auto_cash']
    
    # Check if already enabled
    if auto_cash.get('enabled', False):
        embed = discord.Embed(
            title="[INFO] Already Enabled",
            description="Auto-cash is already enabled!",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="Current Status",
            value="[ENABLED] Running",
            inline=False
        )
        embed.add_field(
            name="Next Execution",
            value=f"Today at `{auto_cash.get('time', 'Not set')}`",
            inline=False
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    # Validate configuration before enabling
    issues = []
    channel_id = auto_cash.get('channel_id', '')
    time_value = auto_cash.get('time', '')
    template = auto_cash.get('command_template', '')
    amounts = auto_cash.get('amounts', {})
    
    if not channel_id:
        issues.append("Channel ID is not set")
    if not time_value:
        issues.append("Execution time is not set")
    if not template:
        issues.append("Command template is not set")
    if '{amount}' not in template:
        issues.append("Command template is missing {amount} placeholder")
    if not amounts or len(amounts) < 7:
        issues.append(f"Only {len(amounts)}/7 weekday amounts configured")
    
    if issues:
        embed = discord.Embed(
            title="[ERROR] Cannot Enable Auto-Cash",
            description="Auto-cash configuration is incomplete!",
            color=discord.Color.red()
        )
        embed.add_field(
            name="Issues Found",
            value="\n".join([f"• {issue}" for issue in issues]),
            inline=False
        )
        embed.add_field(
            name="Fix These Issues",
            value=(
                "Use `/autocash-config` to set missing values\n\n"
                "Example:\n"
                "`/autocash-config time: 12:00 AM channel_id: 123456789 all_days: 1e10`"
            ),
            inline=False
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        logger.warning(f"[WARNING] Auto-cash enable failed - incomplete configuration")
        return
    
    # Enable auto-cash
    auto_cash['enabled'] = True
    
    if bot.config_manager.save_config(config):
        embed = discord.Embed(
            title="[SUCCESS] Auto-Cash Enabled",
            description="Auto-cash has been successfully enabled!",
            color=discord.Color.green(),
            timestamp=datetime.utcnow()
        )
        
        embed.add_field(
            name="Status",
            value="[ENABLED] Active",
            inline=True
        )
        
        embed.add_field(
            name="Execution Time",
            value=f"`{time_value}` IST",
            inline=True
        )
        
        embed.add_field(
            name="Channel",
            value=f"<#{channel_id}>",
            inline=True
        )
        
        # Show today's amount
        ist_tz = pytz.timezone('Asia/Kolkata')
        current_time = datetime.now(ist_tz)
        weekdays = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        today = weekdays[current_time.weekday()]
        today_amount = amounts.get(today, 'Not set')
        
        embed.add_field(
            name=f"Next Execution (Today - {today})",
            value=f"Amount: `{today_amount}`\nCommand: `{template.format(amount=today_amount)}`",
            inline=False
        )
        
        embed.set_footer(text="Scheduler will execute at the configured time daily")
        
        logger.info(f"[SUCCESS] Auto-cash enabled by {interaction.user.name}")
    else:
        embed = discord.Embed(
            title="[ERROR] Failed to Enable",
            description="Could not save configuration!",
            color=discord.Color.red()
        )
        logger.error(f"[ERROR] Failed to save auto-cash enable")
    
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="autocash-disable", description="Disable auto-cash feature")
@is_admin()
async def autocash_disable(interaction: discord.Interaction):
    """Disable auto-cash"""
    logger.info(f"[COMMAND] /autocash-disable executed by {interaction.user.name}")
    
    config = bot.config_manager.load_config()
    
    # Check if auto_cash exists
    if 'auto_cash' not in config:
        embed = discord.Embed(
            title="[INFO] Already Disabled",
            description="Auto-cash is not configured (already disabled).",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    auto_cash = config['auto_cash']
    
    # Check if already disabled
    if not auto_cash.get('enabled', False):
        embed = discord.Embed(
            title="[INFO] Already Disabled",
            description="Auto-cash is already disabled!",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="Current Status",
            value="[DISABLED] Not running",
            inline=False
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    # Disable auto-cash
    old_time = auto_cash.get('time', 'N/A')
    old_channel = auto_cash.get('channel_id', 'N/A')
    auto_cash['enabled'] = False
    
    if bot.config_manager.save_config(config):
        embed = discord.Embed(
            title="[SUCCESS] Auto-Cash Disabled",
            description="Auto-cash has been successfully disabled!",
            color=discord.Color.orange(),
            timestamp=datetime.utcnow()
        )
        
        embed.add_field(
            name="Status",
            value="[DISABLED] Inactive",
            inline=True
        )
        
        embed.add_field(
            name="Previous Time",
            value=f"`{old_time}`",
            inline=True
        )
        
        embed.add_field(
            name="Previous Channel",
            value=f"<#{old_channel}>",
            inline=True
        )
        
        embed.add_field(
            name="[INFO] Configuration Preserved",
            value=(
                "All settings are saved and can be restored by enabling again.\n\n"
                "To re-enable: `/autocash-enable`"
            ),
            inline=False
        )
        
        embed.set_footer(text="No auto-cash commands will be sent until re-enabled")
        
        logger.info(f"[SUCCESS] Auto-cash disabled by {interaction.user.name}")
    else:
        embed = discord.Embed(
            title="[ERROR] Failed to Disable",
            description="Could not save configuration!",
            color=discord.Color.red()
        )
        logger.error(f"[ERROR] Failed to save auto-cash disable")
    
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="autocash-config", description="Configure auto-cash settings")
@app_commands.describe(
    time="Execution time (e.g., '12:00 AM', '14:30')",
    channel_id="Discord channel ID where commands will be sent",
    command_template="Command template with {amount} placeholder",
    monday="Amount for Monday",
    tuesday="Amount for Tuesday",
    wednesday="Amount for Wednesday",
    thursday="Amount for Thursday",
    friday="Amount for Friday",
    saturday="Amount for Saturday",
    sunday="Amount for Sunday",
    all_days="Set same amount for all weekdays (overrides individual days)"
)
@is_admin()
async def autocash_config(
    interaction: discord.Interaction,
    time: str = None,
    channel_id: str = None,
    command_template: str = None,
    monday: str = None,
    tuesday: str = None,
    wednesday: str = None,
    thursday: str = None,
    friday: str = None,
    saturday: str = None,
    sunday: str = None,
    all_days: str = None
):
    """Configure auto-cash settings"""
    logger.info(f"[COMMAND] /autocash-config executed by {interaction.user.name}")
    
    # Check if at least one parameter was provided
    if all(param is None for param in [time, channel_id, command_template, monday, tuesday, wednesday, thursday, friday, saturday, sunday, all_days]):
        embed = discord.Embed(
            title="[ERROR] No Parameters Provided",
            description="Please provide at least one parameter to update!",
            color=discord.Color.red()
        )
        embed.add_field(
            name="Usage Examples",
            value=(
                "`/autocash-config time: 12:00 AM`\n"
                "`/autocash-config channel_id: 123456789`\n"
                "`/autocash-config monday: 1e10 friday: 2e10`\n"
                "`/autocash-config all_days: 1e10`\n"
                "`/autocash-config time: 5:00 PM all_days: 5e10`"
            ),
            inline=False
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    # Load current config
    config = bot.config_manager.load_config()
    
    # Ensure auto_cash section exists
    if 'auto_cash' not in config:
        config['auto_cash'] = {
            'enabled': False,
            'time': '12:00 AM',
            'channel_id': '',
            'command_template': '$add-cash {amount}',
            'amounts': {}
        }
    
    auto_cash = config['auto_cash']
    changes_made = []
    
    # Update time
    if time:
        # Validate time format
        try:
            # Get the scheduler module
            scheduler_path = os.path.join(os.path.dirname(__file__), 'discord_scheduler.py')
            if os.path.exists(scheduler_path):
                import importlib.util
                spec = importlib.util.spec_from_file_location("discord_scheduler", scheduler_path)
                scheduler_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(scheduler_module)
                temp_scheduler = scheduler_module.DiscordPermissionScheduler('config.json')
                temp_scheduler.parse_time_format(time)  # Will raise ValueError if invalid
            
            old_time = auto_cash.get('time', 'Not set')
            auto_cash['time'] = time
            changes_made.append(f"Time: `{old_time}` → `{time}`")
            logger.info(f"[CONFIG] Auto-cash time updated: {time}")
        except ValueError as e:
            embed = discord.Embed(
                title="[ERROR] Invalid Time Format",
                description=f"The time format `{time}` is invalid!\n\nError: {str(e)}",
                color=discord.Color.red()
            )
            embed.add_field(
                name="Valid Time Formats",
                value=(
                    "`12:00 AM` - Midnight (12-hour)\n"
                    "`9:30 PM` - Evening (12-hour)\n"
                    "`00:00` - Midnight (24-hour)\n"
                    "`14:30` - 2:30 PM (24-hour)"
                ),
                inline=False
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        except Exception as e:
            # If validation fails, just accept the time
            logger.warning(f"[WARNING] Could not validate time format: {e}")
            old_time = auto_cash.get('time', 'Not set')
            auto_cash['time'] = time
            changes_made.append(f"Time: `{old_time}` → `{time}`")
    
    # Update channel ID
    if channel_id:
        old_channel = auto_cash.get('channel_id', 'Not set')
        auto_cash['channel_id'] = channel_id
        changes_made.append(f"Channel ID: `{old_channel}` → `{channel_id}`")
        logger.info(f"[CONFIG] Auto-cash channel updated: {channel_id}")
    
    # Update command template
    if command_template:
        old_template = auto_cash.get('command_template', 'Not set')
        
        # Validate that {amount} is in template
        if '{amount}' not in command_template:
            embed = discord.Embed(
                title="[WARNING] Missing {amount} Placeholder",
                description=(
                    "Your command template doesn't contain `{amount}` placeholder!\n\n"
                    "The amount won't be inserted into the command."
                ),
                color=discord.Color.orange()
            )
            embed.add_field(
                name="Your Template",
                value=f"`{command_template}`",
                inline=False
            )
            embed.add_field(
                name="Recommended",
                value=f"`{command_template} {{amount}}`",
                inline=False
            )
            embed.set_footer(text="Update the command to include {amount} somewhere")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        auto_cash['command_template'] = command_template
        changes_made.append(f"Command Template Updated")
        logger.info(f"[CONFIG] Auto-cash template updated: {command_template}")
    
    # Ensure amounts dict exists
    if 'amounts' not in auto_cash:
        auto_cash['amounts'] = {}
    
    # Update amounts
    weekday_map = {
        'monday': ('Monday', monday),
        'tuesday': ('Tuesday', tuesday),
        'wednesday': ('Wednesday', wednesday),
        'thursday': ('Thursday', thursday),
        'friday': ('Friday', friday),
        'saturday': ('Saturday', saturday),
        'sunday': ('Sunday', sunday)
    }
    
    # If all_days is set, apply to all weekdays
    if all_days:
        for day_name, _ in weekday_map.values():
            old_amount = auto_cash['amounts'].get(day_name, 'Not set')
            auto_cash['amounts'][day_name] = all_days
        changes_made.append(f"All Days: Set to `{all_days}`")
        logger.info(f"[CONFIG] All weekday amounts set to: {all_days}")
    else:
        # Update individual days
        for key, (day_name, amount) in weekday_map.items():
            if amount:
                old_amount = auto_cash['amounts'].get(day_name, 'Not set')
                auto_cash['amounts'][day_name] = amount
                changes_made.append(f"{day_name}: `{old_amount}` → `{amount}`")
                logger.info(f"[CONFIG] {day_name} amount updated: {amount}")
    
    # Save config
    if bot.config_manager.save_config(config):
        embed = discord.Embed(
            title="[SUCCESS] Auto-Cash Configuration Updated",
            description=f"Successfully updated {len(changes_made)} setting(s)!",
            color=discord.Color.green(),
            timestamp=datetime.utcnow()
        )
        
        # Show changes
        changes_text = "\n".join([f"• {change}" for change in changes_made])
        embed.add_field(
            name="Changes Made",
            value=changes_text if changes_text else "No changes",
            inline=False
        )
        
        # Show current full config
        current_config = (
            f"**Status:** {'[ENABLED]' if auto_cash.get('enabled', False) else '[DISABLED]'}\n"
            f"**Time:** `{auto_cash.get('time', 'Not set')}`\n"
            f"**Channel:** `{auto_cash.get('channel_id', 'Not set')}`\n"
            f"**Template:** `{auto_cash.get('command_template', 'Not set')}`\n"
            f"**Amounts:**\n"
        )
        
        for day in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']:
            amount = auto_cash.get('amounts', {}).get(day, 'Not set')
            current_config += f"  • {day}: `{amount}`\n"
        
        embed.add_field(
            name="Current Configuration",
            value=current_config,
            inline=False
        )
        
        embed.set_footer(text="Use /autocash-enable to start or /autocash-view for full details")
        
        logger.info(f"[SUCCESS] Auto-cash config updated by {interaction.user.name}")
    else:
        embed = discord.Embed(
            title="[ERROR] Failed to Save",
            description="Could not save configuration to file!",
            color=discord.Color.red()
        )
        logger.error(f"[ERROR] Failed to save auto-cash config")
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ===========================
# CASH CHECKS MANAGEMENT COMMANDS
# ===========================

@bot.tree.command(name="cashcheck-view", description="View current cash check configuration")
@is_admin()
async def cashcheck_view(interaction: discord.Interaction):
    """View cash check configuration"""
    logger.info(f"[COMMAND] /cashcheck-view executed by {interaction.user.name}")
    
    config = bot.config_manager.load_config()
    cash_checks = config.get('cash_checks', {})
    
    # Check if cash checks exists
    if not cash_checks:
        embed = discord.Embed(
            title="🔍 [INFO] Cash Checks Not Configured",
            description="Cash checks monitoring has not been set up yet!",
            color=discord.Color.orange()
        )
        embed.add_field(
            name="Get Started",
            value=(
                "Use `/config` to configure cash check settings\n"
                "Example: `/config setting: cashcheck_interval value: 5`"
            ),
            inline=False
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    # Get status
    enabled = cash_checks.get('enabled', False)
    status_emoji = "✅ [ENABLED]" if enabled else "❌ [DISABLED]"
    status_color = discord.Color.green() if enabled else discord.Color.red()
    
    embed = discord.Embed(
        title=f"🔍 {status_emoji} Cash Checks Configuration",
        description=f"Automatic cash limit monitoring and auto-add",
        color=status_color,
        timestamp=datetime.utcnow()
    )
    
    # Status
    embed.add_field(
        name="📊 Status",
        value=f"**{'✅ Monitoring Active' if enabled else '❌ Disabled'}**",
        inline=True
    )
    
    # Check Interval
    interval = cash_checks.get('check_interval_minutes', 'Not set')
    embed.add_field(
        name="⏱️ Check Interval",
        value=f"`{interval}` minutes",
        inline=True
    )
    
    # Bot ID
    bot_id = cash_checks.get('bot_id', 'Not set')
    embed.add_field(
        name="🤖 Bot ID",
        value=f"`{bot_id}`",
        inline=True
    )
    
    # Channel
    channel_id = cash_checks.get('channel_id', 'Not set')
    if channel_id != 'Not set':
        embed.add_field(
            name="📍 Monitoring Channel",
            value=f"<#{channel_id}>\n`{channel_id}`",
            inline=False
        )
    else:
        embed.add_field(
            name="📍 Monitoring Channel",
            value="`Not set`",
            inline=False
        )
    
    # Command Template
    command = cash_checks.get('command', 'Not set')
    embed.add_field(
        name="💰 Add-Cash Command",
        value=f"`{command}`",
        inline=False
    )
    
    # Check if {amount} is in command
    if command != 'Not set' and '{amount}' not in command:
        embed.add_field(
            name="⚠️ [WARNING] Command Issue",
            value="Command is missing `{amount}` placeholder!",
            inline=False
        )
    
    # How it works
    auto_cash = config.get('auto_cash', {})
    if auto_cash.get('amounts'):
        # Calculate example for today
        ist_tz = pytz.timezone('Asia/Kolkata')
        current_time = datetime.now(ist_tz)
        weekdays = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        today = weekdays[current_time.weekday()]
        
        # Get weekday order from auto_cash
        weekday_order = list(auto_cash.get('amounts', {}).keys())
        if today in weekday_order:
            current_position = weekday_order.index(today)
            
            # Calculate cumulative
            cumulative = 0
            for i in range(current_position + 1):
                day_name = weekday_order[i]
                amount_str = auto_cash['amounts'].get(day_name, 0)
                try:
                    amount = int(float(amount_str))
                    cumulative += amount
                except:
                    pass
            
            embed.add_field(
                name=f"📈 Today's Limit ({today})",
                value=(
                    f"Cumulative Limit: `{cumulative:,}`\n"
                    f"Will add cash if top user has less than this amount"
                ),
                inline=False
            )
    
    # Configuration completeness check
    issues = []
    if not enabled:
        issues.append("Cash checks are disabled")
    if channel_id == 'Not set':
        issues.append("Channel ID not set")
    if interval == 'Not set':
        issues.append("Check interval not set")
    if command == 'Not set':
        issues.append("Command template not set")
    if bot_id == 'Not set':
        issues.append("Bot ID not set")
    
    if issues:
        embed.add_field(
            name="ℹ️ Configuration Status",
            value="\n".join([f"• {issue}" for issue in issues]),
            inline=False
        )
    else:
        embed.add_field(
            name="✅ Configuration Status",
            value="All settings configured correctly!",
            inline=False
        )
    
    # Process explanation
    embed.add_field(
        name="🔄 How It Works",
        value=(
            "1️⃣ Every `interval` minutes, sends `$lb -cash`\n"
            "2️⃣ Fetches bot response and parses top user's cash\n"
            "3️⃣ Calculates cumulative limit from auto-cash config\n"
            "4️⃣ If current < limit, sends add-cash command\n"
            "5️⃣ Logs all actions for monitoring"
        ),
        inline=False
    )
    
    embed.set_footer(text="Use /config to modify settings | /cashcheck-enable or /cashcheck-disable to toggle")
    
    await interaction.response.send_message(embed=embed, ephemeral=True)
    logger.info(f"[INFO] Cash check config displayed to {interaction.user.name}")


@bot.tree.command(name="cashcheck-enable", description="Enable cash checks monitoring")
@is_admin()
async def cashcheck_enable(interaction: discord.Interaction):
    """Enable cash checks"""
    logger.info(f"[COMMAND] /cashcheck-enable executed by {interaction.user.name}")
    
    config = bot.config_manager.load_config()
    
    # Ensure cash_checks section exists
    if 'cash_checks' not in config:
        config['cash_checks'] = {
            'enabled': False,
            'check_interval_minutes': 5,
            'channel_id': '',
            'bot_id': '292953664492929025',
            'command': '$add-cash {amount}'
        }
    
    cash_checks = config['cash_checks']
    
    # Check if already enabled
    if cash_checks.get('enabled', False):
        embed = discord.Embed(
            title="ℹ️ [INFO] Already Enabled",
            description="Cash checks are already enabled!",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="Current Status",
            value="✅ [ENABLED] Monitoring active",
            inline=False
        )
        embed.add_field(
            name="Check Interval",
            value=f"Every `{cash_checks.get('check_interval_minutes', 5)}` minutes",
            inline=False
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    # Validate configuration before enabling
    issues = []
    channel_id = cash_checks.get('channel_id', '')
    interval = cash_checks.get('check_interval_minutes', 0)
    command = cash_checks.get('command', '')
    bot_id = cash_checks.get('bot_id', '')
    
    if not channel_id:
        issues.append("Channel ID is not set")
    if not interval or interval <= 0:
        issues.append("Check interval is invalid")
    if not command:
        issues.append("Command template is not set")
    if '{amount}' not in command:
        issues.append("Command template is missing {amount} placeholder")
    if not bot_id:
        issues.append("Bot ID is not set")
    
    # Check if auto-cash is configured (needed for limit calculation)
    auto_cash = config.get('auto_cash', {})
    if not auto_cash.get('amounts'):
        issues.append("Auto-cash amounts not configured (needed for limit calculation)")
    
    if issues:
        embed = discord.Embed(
            title="❌ [ERROR] Cannot Enable Cash Checks",
            description="Cash checks configuration is incomplete!",
            color=discord.Color.red()
        )
        embed.add_field(
            name="Issues Found",
            value="\n".join([f"• {issue}" for issue in issues]),
            inline=False
        )
        embed.add_field(
            name="Fix These Issues",
            value=(
                "Use `/config` to set missing values\n\n"
                "Example:\n"
                "`/config setting: cashcheck_channel value: 123456789`\n"
                "`/config setting: cashcheck_interval value: 5`"
            ),
            inline=False
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        logger.warning(f"[WARNING] Cash checks enable failed - incomplete configuration")
        return
    
    # Enable cash checks
    cash_checks['enabled'] = True
    
    if bot.config_manager.save_config(config):
        embed = discord.Embed(
            title="✅ [SUCCESS] Cash Checks Enabled",
            description="Cash checks monitoring has been successfully enabled!",
            color=discord.Color.green(),
            timestamp=datetime.utcnow()
        )
        
        embed.add_field(
            name="📊 Status",
            value="✅ [ENABLED] Active",
            inline=True
        )
        
        embed.add_field(
            name="⏱️ Check Every",
            value=f"`{interval}` minutes",
            inline=True
        )
        
        embed.add_field(
            name="📍 Channel",
            value=f"<#{channel_id}>",
            inline=True
        )
        
        embed.add_field(
            name="🔄 What Happens Now",
            value=(
                f"Every **{interval} minutes**, the bot will:\n"
                "1. Check top user's cash via `$lb -cash`\n"
                "2. Compare with cumulative limit\n"
                "3. Auto-add cash if below limit\n"
                "4. Log all actions"
            ),
            inline=False
        )
        
        embed.set_footer(text="Monitoring will start within the next check interval")
        
        logger.info(f"[SUCCESS] Cash checks enabled by {interaction.user.name}")
    else:
        embed = discord.Embed(
            title="❌ [ERROR] Failed to Enable",
            description="Could not save configuration!",
            color=discord.Color.red()
        )
        logger.error(f"[ERROR] Failed to save cash checks enable")
    
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="cashcheck-disable", description="Disable cash checks monitoring")
@is_admin()
async def cashcheck_disable(interaction: discord.Interaction):
    """Disable cash checks"""
    logger.info(f"[COMMAND] /cashcheck-disable executed by {interaction.user.name}")
    
    config = bot.config_manager.load_config()
    
    # Check if cash_checks exists
    if 'cash_checks' not in config:
        embed = discord.Embed(
            title="ℹ️ [INFO] Already Disabled",
            description="Cash checks are not configured (already disabled).",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    cash_checks = config['cash_checks']
    
    # Check if already disabled
    if not cash_checks.get('enabled', False):
        embed = discord.Embed(
            title="ℹ️ [INFO] Already Disabled",
            description="Cash checks are already disabled!",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="Current Status",
            value="❌ [DISABLED] Not monitoring",
            inline=False
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    # Disable cash checks
    old_interval = cash_checks.get('check_interval_minutes', 'N/A')
    old_channel = cash_checks.get('channel_id', 'N/A')
    cash_checks['enabled'] = False
    
    if bot.config_manager.save_config(config):
        embed = discord.Embed(
            title="⚠️ [SUCCESS] Cash Checks Disabled",
            description="Cash checks monitoring has been successfully disabled!",
            color=discord.Color.orange(),
            timestamp=datetime.utcnow()
        )
        
        embed.add_field(
            name="📊 Status",
            value="❌ [DISABLED] Inactive",
            inline=True
        )
        
        embed.add_field(
            name="Previous Interval",
            value=f"`{old_interval}` min",
            inline=True
        )
        
        embed.add_field(
            name="Previous Channel",
            value=f"<#{old_channel}>",
            inline=True
        )
        
        embed.add_field(
            name="ℹ️ Configuration Preserved",
            value=(
                "All settings are saved and can be restored by enabling again.\n\n"
                "To re-enable: `/cashcheck-enable`"
            ),
            inline=False
        )
        
        embed.set_footer(text="No cash checks will be performed until re-enabled")
        
        logger.info(f"[SUCCESS] Cash checks disabled by {interaction.user.name}")
    else:
        embed = discord.Embed(
            title="❌ [ERROR] Failed to Disable",
            description="Could not save configuration!",
            color=discord.Color.red()
        )
        logger.error(f"[ERROR] Failed to save cash checks disable")
    
    await interaction.response.send_message(embed=embed, ephemeral=True)


# ===========================
# UNIFIED SETTINGS COMMAND
# ===========================

@bot.tree.command(name="config", description="Configure any bot setting")
@app_commands.describe(
    setting="Setting to configure",
    value="New value for the setting"
)
@app_commands.choices(setting=[
    # Auto-cash settings
    app_commands.Choice(name="AutoCash: Time", value="autocash_time"),
    app_commands.Choice(name="AutoCash: Channel", value="autocash_channel"),
    app_commands.Choice(name="AutoCash: Command Template", value="autocash_command"),
    app_commands.Choice(name="AutoCash: Amount (All Days)", value="autocash_amount_all"),
    app_commands.Choice(name="AutoCash: Monday Amount", value="autocash_monday"),
    app_commands.Choice(name="AutoCash: Tuesday Amount", value="autocash_tuesday"),
    app_commands.Choice(name="AutoCash: Wednesday Amount", value="autocash_wednesday"),
    app_commands.Choice(name="AutoCash: Thursday Amount", value="autocash_thursday"),
    app_commands.Choice(name="AutoCash: Friday Amount", value="autocash_friday"),
    app_commands.Choice(name="AutoCash: Saturday Amount", value="autocash_saturday"),
    app_commands.Choice(name="AutoCash: Sunday Amount", value="autocash_sunday"),
    
    # Cash checks settings
    app_commands.Choice(name="CashCheck: Interval (minutes)", value="cashcheck_interval"),
    app_commands.Choice(name="CashCheck: Channel", value="cashcheck_channel"),
    app_commands.Choice(name="CashCheck: Bot ID", value="cashcheck_botid"),
    app_commands.Choice(name="CashCheck: Command", value="cashcheck_command"),
    
    # Messages
    app_commands.Choice(name="Message: Opening (Unlock)", value="message_opening"),
    app_commands.Choice(name="Message: Closing (Lock)", value="message_closing"),
])
@is_admin()
async def unified_config(interaction: discord.Interaction, setting: str, value: str):
    """Unified configuration command"""
    logger.info(f"[COMMAND] /config executed by {interaction.user.name}: {setting} = {value}")
    
    config = bot.config_manager.load_config()
    
    # Ensure sections exist
    if 'auto_cash' not in config:
        config['auto_cash'] = {'enabled': False, 'amounts': {}}
    if 'cash_checks' not in config:
        config['cash_checks'] = {'enabled': False}
    
    setting_name = ""
    old_value = ""
    
    # Auto-cash settings
    if setting == "autocash_time":
        old_value = config['auto_cash'].get('time', 'Not set')
        config['auto_cash']['time'] = value
        setting_name = "Auto-Cash Time"
    
    elif setting == "autocash_channel":
        old_value = config['auto_cash'].get('channel_id', 'Not set')
        config['auto_cash']['channel_id'] = value
        setting_name = "Auto-Cash Channel"
    
    elif setting == "autocash_command":
        old_value = config['auto_cash'].get('command_template', 'Not set')
        if '{amount}' not in value:
            embed = discord.Embed(
                title="⚠️ [WARNING] Missing Placeholder",
                description=f"Command template should contain `{{amount}}` placeholder!\n\nYour value: `{value}`",
                color=discord.Color.orange()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        config['auto_cash']['command_template'] = value
        setting_name = "Auto-Cash Command Template"
    
    elif setting == "autocash_amount_all":
        old_value = "Individual settings"
        for day in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']:
            config['auto_cash']['amounts'][day] = value
        setting_name = "All Weekday Amounts"
    
    elif setting.startswith("autocash_"):
        day_map = {
            'autocash_monday': 'Monday',
            'autocash_tuesday': 'Tuesday',
            'autocash_wednesday': 'Wednesday',
            'autocash_thursday': 'Thursday',
            'autocash_friday': 'Friday',
            'autocash_saturday': 'Saturday',
            'autocash_sunday': 'Sunday'
        }
        day = day_map.get(setting)
        if day:
            old_value = config['auto_cash']['amounts'].get(day, 'Not set')
            config['auto_cash']['amounts'][day] = value
            setting_name = f"Auto-Cash {day} Amount"
    
    # Cash checks settings
    elif setting == "cashcheck_interval":
        old_value = str(config['cash_checks'].get('check_interval_minutes', 'Not set'))
        try:
            interval = int(value)
            if interval <= 0:
                raise ValueError("Interval must be positive")
            config['cash_checks']['check_interval_minutes'] = interval
            setting_name = "Cash Check Interval"
        except ValueError:
            embed = discord.Embed(
                title="❌ [ERROR] Invalid Value",
                description=f"Interval must be a positive number!\n\nYou entered: `{value}`",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
    
    elif setting == "cashcheck_channel":
        old_value = config['cash_checks'].get('channel_id', 'Not set')
        config['cash_checks']['channel_id'] = value
        setting_name = "Cash Check Channel"
    
    elif setting == "cashcheck_botid":
        old_value = config['cash_checks'].get('bot_id', 'Not set')
        config['cash_checks']['bot_id'] = value
        setting_name = "Cash Check Bot ID"
    
    elif setting == "cashcheck_command":
        old_value = config['cash_checks'].get('command', 'Not set')
        if '{amount}' not in value:
            embed = discord.Embed(
                title="⚠️ [WARNING] Missing Placeholder",
                description=f"Command should contain `{{amount}}` placeholder!\n\nYour value: `{value}`",
                color=discord.Color.orange()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        config['cash_checks']['command'] = value
        setting_name = "Cash Check Command"
    
    # Messages
    elif setting == "message_opening":
        old_value = config.get('opening_message', 'Not set')
        config['opening_message'] = value
        setting_name = "Opening Message"
    
    elif setting == "message_closing":
        old_value = config.get('closing_message', 'Not set')
        config['closing_message'] = value
        setting_name = "Closing Message"
    
    # Save configuration
    if bot.config_manager.save_config(config):
        embed = discord.Embed(
            title="✅ [SUCCESS] Setting Updated",
            description=f"**{setting_name}** has been updated!",
            color=discord.Color.green(),
            timestamp=datetime.utcnow()
        )
        
        embed.add_field(
            name="Setting",
            value=f"`{setting_name}`",
            inline=False
        )
        
        embed.add_field(
            name="Old Value",
            value=f"```{old_value}```" if old_value else "`Not set`",
            inline=True
        )
        
        embed.add_field(
            name="New Value",
            value=f"```{value}```",
            inline=True
        )
        
        # Add tip based on setting type
        if setting.startswith("autocash"):
            embed.set_footer(text="Use /autocash-view to see full configuration | /autocash-enable to activate")
        elif setting.startswith("cashcheck"):
            embed.set_footer(text="Use /cashcheck-view to see full configuration | /cashcheck-enable to activate")
        elif setting.startswith("message"):
            embed.set_footer(text="Use /view-messages to see all messages")
        
        logger.info(f"[SUCCESS] Setting '{setting_name}' updated: {old_value} → {value}")
    else:
        embed = discord.Embed(
            title="❌ [ERROR] Failed to Save",
            description="Could not save configuration!",
            color=discord.Color.red()
        )
        logger.error(f"[ERROR] Failed to save config for setting: {setting}")
    
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="help", description="Show all available commands")
async def help_command(interaction: discord.Interaction):
    """Show help"""
    logger.info(f"[COMMAND] /help executed by {interaction.user.name}")
    
    embed = discord.Embed(
        title="📚 [HELP] Scheduler Bot Help",
        description="Manage scheduled tasks for Discord channel permissions\n\n**All commands are slash commands only!**",
        color=discord.Color.blue(),
        timestamp=datetime.utcnow()
    )
    
    # View Commands
    embed.add_field(
        name="👀 [VIEW] View Commands",
        value=(
            "`/tasks` - List all scheduled tasks\n"
            "`/task-info` - Get detailed task information\n"
            "`/view-messages` - View opening/closing messages\n"
            "`/autocash-view` - View auto-cash configuration\n"
            "`/cashcheck-view` - View cash check configuration\n"
            "`/export-config` - Export configuration file"
        ),
        inline=False
    )
    
    # Add Commands
    embed.add_field(
        name="➕ [ADD] Add Commands",
        value=(
            "`/add-lock-task` - Add a channel lock task\n"
            "`/add-unlock-task` - Add a channel unlock task"
        ),
        inline=False
    )
    
    # Modify Commands
    embed.add_field(
        name="✏️ [MODIFY] Modify Commands",
        value=(
            "`/update-task-time` - Update task execution time\n"
            "`/remove-task` - Remove a specific task\n"
            "`/clear-all-tasks` - Remove ALL tasks"
        ),
        inline=False
    )
    
    # Message Configuration
    embed.add_field(
        name="💬 [MESSAGES] Message Configuration",
        value=(
            "`/set-opening-message` - Set default unlock message\n"
            "`/set-closing-message` - Set default lock message\n"
            "`/view-messages` - View current messages"
        ),
        inline=False
    )

    # Auto-Cash Management
    embed.add_field(
        name="💰 [AUTOCASH] Auto-Cash Management",
        value=(
            "`/autocash-view` - View auto-cash configuration\n"
            "`/autocash-enable` - Enable auto-cash feature\n"
            "`/autocash-disable` - Disable auto-cash feature\n"
            "`/autocash-config` - Configure auto-cash settings"
        ),
        inline=False
    )
    
    # Cash Checks Management
    embed.add_field(
        name="🔍 [CASHCHECK] Cash Checks Monitoring",
        value=(
            "`/cashcheck-view` - View cash check configuration\n"
            "`/cashcheck-enable` - Enable cash checks monitoring\n"
            "`/cashcheck-disable` - Disable cash checks\n"
        ),
        inline=False
    )
    
    # Unified Config
    embed.add_field(
        name="⚙️ [CONFIG] Unified Settings",
        value=(
            "`/config` - Configure any setting\n"
            "Use dropdown to select setting type"
        ),
        inline=False
    )
    
    # Time Format Examples
    embed.add_field(
        name="⏰ [TIME] Time Format Examples",
        value=(
            "`Monday 10:30pm` - Monday at 10:30 PM\n"
            "`Thursday 14:30` - Thursday at 2:30 PM\n"
            "`9:00am` - Every day at 9:00 AM\n"
            "`17:45` - Every day at 5:45 PM (24h format)"
        ),
        inline=False
    )
    
    embed.set_footer(text="Use slash commands (/) to access all features - Admin only")
    
    await interaction.response.send_message(embed=embed, ephemeral=True)
    logger.info(f"[INFO] Help displayed to {interaction.user.name}")

# ===========================
# AUTOCOMPLETE
# ===========================

@task_info.autocomplete('task_name')
@remove_task.autocomplete('task_name')
@update_task_time.autocomplete('task_name')
async def task_name_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    """Autocomplete for task names"""
    tasks = bot.config_manager.list_tasks()
    choices = [
        app_commands.Choice(name=task_name, value=task_name)
        for task_name in tasks.keys()
        if current.lower() in task_name.lower()
    ][:25]  # Discord limits to 25 choices
    
    logger.debug(f"[DEBUG] Autocomplete provided {len(choices)} choices for input: {current}")
    return choices


# ===========================
# ERROR HANDLERS
# ===========================

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    """Handle command errors"""
    if isinstance(error, app_commands.CheckFailure):
        # Already handled in the check
        return
    
    logger.error(f"[ERROR] Command error from {interaction.user.name}: {error}", exc_info=True)
    
    embed = discord.Embed(
        title="[ERROR] Command Error",
        description=f"An error occurred: {str(error)}",
        color=discord.Color.red()
    )
    
    try:
        if not interaction.response.is_done():
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.followup.send(embed=embed, ephemeral=True)
    except Exception as e:
        logger.error(f"[ERROR] Could not send error message to user: {e}")


@bot.event
async def on_command_error(ctx, error):
    """Handle prefix command errors (this should never fire since we have no prefix commands)"""
    logger.error(f"[ERROR] Unexpected command error: {error}")


@bot.event
async def on_guild_join(guild):
    """Log when bot joins a guild"""
    logger.info(f"[EVENT] Bot joined guild: {guild.name} (ID: {guild.id})")


@bot.event
async def on_guild_remove(guild):
    """Log when bot leaves a guild"""
    logger.info(f"[EVENT] Bot removed from guild: {guild.name} (ID: {guild.id})")


# ===========================
# MAIN
# ===========================

if __name__ == "__main__":
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    
    if not BOT_TOKEN:
        logger.error("[ERROR] BOT_TOKEN not found in .env file!")
        logger.error("[ERROR] Please add BOT_TOKEN=your_token_here to your .env file")
        exit(1)
    
    logger.info("=" * 60)
    logger.info("[START] Starting Scheduler Management Bot...")
    logger.info("[INFO] Mode: Slash Commands Only")
    logger.info("=" * 60)
    
    try:
        bot.run(BOT_TOKEN)
    except discord.LoginFailure:
        logger.error("[ERROR] Invalid bot token!")
    except KeyboardInterrupt:
        logger.info("[STOP] Bot stopped by user (Ctrl+C)")
    except Exception as e:
        logger.error(f"[ERROR] Failed to start bot: {e}", exc_info=True)