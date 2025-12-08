# Discord Scheduler Bot - Auto-Deployed via GitHub Actions
import json
import requests
import pytz
import schedule
import time
from datetime import datetime, timedelta
import logging
import re
import random
from typing import Dict, Any, Optional
from dotenv import load_dotenv
import os
import threading
import asyncio

# Load environment variables
load_dotenv()

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('discord_scheduler.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)


class DiscordPermissionScheduler:
    """
    Production-grade Discord channel permission scheduler
    Uses User token authentication only
    
    Features:
    - Channel lock/unlock scheduling
    - Auto-cash daily distribution
    - Cash limit checking
    - Role-based cash distribution (supports scientific notation like 1e10)
    - Typing indicators for human-like behavior
    - AUTO-DISABLE all features on LOCK
    - AUTO-ENABLE all features on UNLOCK
    """
    
    # Default Discord client versions (fallback if auto-fetch fails)
    DISCORD_VERSIONS = {
        'stable': '0.0.309',
        'build_number': '245053',
        'client_version': '2023.1116.0'
    }
    
    # Real User-Agent strings from actual Discord clients
    USER_AGENTS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) discord/0.0.309 Chrome/108.0.5359.215 Electron/22.3.12 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) discord/0.0.309 Chrome/108.0.5359.215 Electron/22.3.12 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) discord/0.0.309 Chrome/108.0.5359.215 Electron/22.3.12 Safari/537.36',
    ]
    
    # Discord API endpoints
    DISCORD_API_BASE = 'https://discord.com/api/v10'
    DISCORD_BUILD_INFO_URL = 'https://discord.com/api/v10/updates?platform=win'
    
    # Weekday mapping
    WEEKDAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    
    # Features that can be toggled on lock/unlock
    TOGGLEABLE_FEATURES = ['auto_cash', 'cash_checks', 'add_cash_to_roles']
    
    def __init__(self, config_file='config.json'):
        self.config_file = config_file
        self.config = self.load_config(config_file)
        self.ist_tz = pytz.timezone('Asia/Kolkata')
        self.last_execution = {}
        self.last_auto_cash_execution = None
        self.last_cash_check_time = None
        self.last_role_cash_time = None
        self.session = self._create_session()
        self.rate_limit_reset = {}
        self.known_tasks = set(self.config.get('tasks', {}).keys())
        self.known_roles = set(self.config.get('add_cash_to_roles', {}).get('roles', {}).keys())
        
        # Store original feature states for reference
        self.original_feature_states = self._get_feature_states()
        
        # Load Discord token from environment variable
        self.discord_token = os.getenv('TOKEN')
        if not self.discord_token:
            logging.error("[ERROR] DISCORD_TOKEN not found in .env file!")
            raise ValueError("DISCORD_TOKEN environment variable is required")
        
        logging.info("[OK] Discord token loaded from .env")
        
        # Fetch latest Discord versions
        self._fetch_discord_versions()
        
        # Log all configurations
        self._log_startup_config()
    
    def _log_startup_config(self):
        """Log all feature configurations at startup"""
        logging.info("=" * 60)
        logging.info("[CONFIG] FEATURE STATES AT STARTUP")
        logging.info("=" * 60)
        
        # Log auto-cash configuration
        auto_cash = self.config.get('auto_cash', {})
        enabled = auto_cash.get('enabled', False)
        logging.info(f"[AUTO-CASH] {'✅ ENABLED' if enabled else '❌ DISABLED'}")
        if enabled:
            logging.info(f"  Time: {auto_cash.get('time')}, Channel: {auto_cash.get('channel_id')}")
        
        # Log cash checks configuration
        cash_checks = self.config.get('cash_checks', {})
        enabled = cash_checks.get('enabled', False)
        logging.info(f"[CASH-CHECK] {'✅ ENABLED' if enabled else '❌ DISABLED'}")
        if enabled:
            logging.info(f"  Interval: {cash_checks.get('check_interval_minutes')} min, Channel: {cash_checks.get('channel_id')}")
        
        # Log add_cash_to_roles configuration
        role_cash = self.config.get('add_cash_to_roles', {})
        enabled = role_cash.get('enabled', False)
        logging.info(f"[ROLE-CASH] {'✅ ENABLED' if enabled else '❌ DISABLED'}")
        if enabled:
            role_count = len(role_cash.get('roles', {}))
            logging.info(f"  Interval: {role_cash.get('check_interval_minutes')} min, Roles: {role_count}")
        
        logging.info("=" * 60)
    
    def _fetch_discord_versions(self):
        """Fetch the latest Discord client version information"""
        try:
            logging.info("[VERSION] Fetching latest Discord client version...")
            
            response = requests.get(
                'https://discord.com/api/v10/updates?platform=win',
                headers={'User-Agent': 'Mozilla/5.0'},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if 'name' in data:
                    version = data['name']
                    self.DISCORD_VERSIONS['stable'] = version
                    logging.info(f"[VERSION] [OK] Fetched Discord version: {version}")
            else:
                response = requests.get(
                    'https://discord.com/app',
                    headers={'User-Agent': 'Mozilla/5.0'},
                    timeout=10
                )
                
                if response.status_code == 200:
                    build_match = re.search(r'"buildNumber":"(\d+)"', response.text)
                    if build_match:
                        build_number = build_match.group(1)
                        self.DISCORD_VERSIONS['build_number'] = build_number
                        logging.info(f"[VERSION] [OK] Fetched build number: {build_number}")
                    
                    version_match = re.search(r'"version":"([0-9.]+)"', response.text)
                    if version_match:
                        version = version_match.group(1)
                        self.DISCORD_VERSIONS['stable'] = version
                        logging.info(f"[VERSION] [OK] Fetched version: {version}")
            
            if self.DISCORD_VERSIONS.get('build_number') == '245053':
                try:
                    manifest_response = requests.get(
                        'https://discord.com/assets/version.stable.json',
                        timeout=10
                    )
                    if manifest_response.status_code == 200:
                        manifest_data = manifest_response.json()
                        if 'build_number' in manifest_data:
                            self.DISCORD_VERSIONS['build_number'] = str(manifest_data['build_number'])
                            logging.info(f"[VERSION] [OK] Fetched build from manifest: {manifest_data['build_number']}")
                except:
                    pass
            
            logging.info(f"[VERSION] Using Discord version: {self.DISCORD_VERSIONS['stable']}")
            logging.info(f"[VERSION] Using build number: {self.DISCORD_VERSIONS['build_number']}")
            
        except Exception as e:
            logging.warning(f"[VERSION] [WARNING] Could not fetch latest Discord version: {str(e)}")
            logging.info(f"[VERSION] Using default version: {self.DISCORD_VERSIONS['stable']}")
            logging.info(f"[VERSION] Using default build: {self.DISCORD_VERSIONS['build_number']}")
    
    def load_config(self, config_file: str) -> Dict:
        """Load configuration from JSON file"""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            logging.info(f"[OK] Configuration loaded from {config_file}")
            return config
        except FileNotFoundError:
            logging.error(f"[ERROR] Config file {config_file} not found!")
            raise
        except json.JSONDecodeError:
            logging.error(f"[ERROR] Invalid JSON in {config_file}")
            raise
    
    def save_config(self) -> bool:
        """
        Save current configuration to JSON file
        
        Returns:
            True if successful, False otherwise
        """
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            logging.info(f"[CONFIG] ✅ Configuration saved to {self.config_file}")
            return True
        except Exception as e:
            logging.error(f"[CONFIG] ❌ Failed to save configuration: {str(e)}")
            return False
    
    def _get_feature_states(self) -> Dict[str, bool]:
        """
        Get current enabled state of all toggleable features
        
        Returns:
            Dict mapping feature names to their enabled state
        """
        states = {}
        for feature in self.TOGGLEABLE_FEATURES:
            feature_config = self.config.get(feature, {})
            states[feature] = feature_config.get('enabled', False)
        return states
    
    def _set_feature_states(self, enabled: bool, save: bool = True) -> bool:
        """
        Set enabled state for all toggleable features
        
        Args:
            enabled: True to enable all features, False to disable all
            save: Whether to save config to file after updating
            
        Returns:
            True if successful, False otherwise
        """
        state_str = "ENABLED" if enabled else "DISABLED"
        
        logging.info("=" * 60)
        logging.info(f"[CONFIG] 🔄 UPDATING ALL FEATURE STATES TO: {state_str}")
        logging.info("=" * 60)
        
        changes_made = []
        
        for feature in self.TOGGLEABLE_FEATURES:
            if feature in self.config:
                old_state = self.config[feature].get('enabled', False)
                self.config[feature]['enabled'] = enabled
                
                old_str = "✅" if old_state else "❌"
                new_str = "✅" if enabled else "❌"
                
                if old_state != enabled:
                    changes_made.append(feature)
                    logging.info(f"[CONFIG] {feature}: {old_str} → {new_str} (CHANGED)")
                else:
                    logging.info(f"[CONFIG] {feature}: {old_str} → {new_str} (no change)")
            else:
                logging.warning(f"[CONFIG] Feature '{feature}' not found in config")
        
        if changes_made:
            logging.info(f"[CONFIG] Features modified: {', '.join(changes_made)}")
        else:
            logging.info(f"[CONFIG] No features were modified (already in desired state)")
        
        if save:
            save_result = self.save_config()
            if save_result:
                logging.info(f"[CONFIG] 💾 Config file updated successfully!")
            else:
                logging.error(f"[CONFIG] ⚠️ Failed to save config to file!")
            return save_result
        
        logging.info("=" * 60)
        return True
    
    def disable_all_features(self, save: bool = True) -> bool:
        """
        Disable all automated features (called on LOCK)
        
        Args:
            save: Whether to save config to file
            
        Returns:
            True if successful, False otherwise
        """
        logging.info("[LOCK] 🔒 Disabling all automated features...")
        return self._set_feature_states(enabled=False, save=save)
    
    def enable_all_features(self, save: bool = True) -> bool:
        """
        Enable all automated features (called on UNLOCK)
        
        Args:
            save: Whether to save config to file
            
        Returns:
            True if successful, False otherwise
        """
        logging.info("[UNLOCK] 🔓 Enabling all automated features...")
        return self._set_feature_states(enabled=True, save=save)
    
    def get_feature_status(self) -> Dict[str, Any]:
        """
        Get detailed status of all features
        
        Returns:
            Dict with feature status information
        """
        status = {
            'features': {},
            'all_enabled': True,
            'all_disabled': True
        }
        
        for feature in self.TOGGLEABLE_FEATURES:
            feature_config = self.config.get(feature, {})
            enabled = feature_config.get('enabled', False)
            
            status['features'][feature] = {
                'enabled': enabled,
                'config': feature_config
            }
            
            if enabled:
                status['all_disabled'] = False
            else:
                status['all_enabled'] = False
        
        return status
    
    def log_feature_status(self):
        """Log current status of all features"""
        status = self.get_feature_status()
        
        logging.info("-" * 40)
        logging.info("[STATUS] Current Feature States:")
        
        for feature, info in status['features'].items():
            enabled = info['enabled']
            icon = "✅" if enabled else "❌"
            state = "ENABLED" if enabled else "DISABLED"
            logging.info(f"  {icon} {feature}: {state}")
        
        logging.info("-" * 40)
    
    def reload_config(self):
        """Reload configuration and detect new tasks/roles"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                new_config = json.load(f)
            
            # Detect task changes
            new_tasks = set(new_config.get('tasks', {}).keys())
            added_tasks = new_tasks - self.known_tasks
            removed_tasks = self.known_tasks - new_tasks
            
            if added_tasks:
                logging.info("=" * 60)
                logging.info(f"[NEW] Detected {len(added_tasks)} NEW task(s):")
                for task_name in added_tasks:
                    task_config = new_config['tasks'][task_name]
                    logging.info(f"  [+] {task_name}: {task_config.get('lock_time')} IST")
                logging.info("=" * 60)
            
            if removed_tasks:
                logging.info("=" * 60)
                logging.info(f"[REMOVED] Detected {len(removed_tasks)} REMOVED task(s):")
                for task_name in removed_tasks:
                    logging.info(f"  [-] {task_name}")
                logging.info("=" * 60)
            
            # Detect role changes
            new_roles = set(new_config.get('add_cash_to_roles', {}).get('roles', {}).keys())
            added_roles = new_roles - self.known_roles
            removed_roles = self.known_roles - new_roles
            
            if added_roles:
                logging.info(f"[ROLE-CASH] Detected {len(added_roles)} NEW role(s): {added_roles}")
            if removed_roles:
                logging.info(f"[ROLE-CASH] Detected {len(removed_roles)} REMOVED role(s): {removed_roles}")
            
            # Detect feature state changes (external changes to config file)
            for feature in self.TOGGLEABLE_FEATURES:
                old_state = self.config.get(feature, {}).get('enabled', False)
                new_state = new_config.get(feature, {}).get('enabled', False)
                
                if old_state != new_state:
                    old_str = "ENABLED" if old_state else "DISABLED"
                    new_str = "ENABLED" if new_state else "DISABLED"
                    logging.info(f"[CONFIG] {feature} state changed externally: {old_str} → {new_str}")
            
            # Update config and known items
            self.config = new_config
            self.known_tasks = new_tasks
            self.known_roles = new_roles
            
            if added_tasks or removed_tasks:
                logging.info(f"[INFO] Total active tasks: {len(self.known_tasks)}")
            
        except Exception as e:
            logging.error(f"[ERROR] Failed to reload config: {str(e)}")
    
    def _create_session(self) -> requests.Session:
        """Create a persistent session with connection pooling"""
        session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=10,
            pool_maxsize=20,
            max_retries=3
        )
        session.mount('https://', adapter)
        return session
    
    def _get_discord_headers(self, token: str) -> Dict[str, str]:
        """Generate realistic Discord API headers for user tokens"""
        user_agent = random.choice(self.USER_AGENTS)
        headers = {
            'Authorization': token,
            'Content-Type': 'application/json',
            'User-Agent': user_agent,
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Origin': 'https://discord.com',
            'Referer': 'https://discord.com/channels/@me',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
            'X-Debug-Options': 'bugReporterEnabled',
            'X-Discord-Locale': 'en-US',
            'X-Discord-Timezone': 'Asia/Kolkata',
            'X-Super-Properties': self._generate_super_properties(),
        }
        
        return headers
    
    def _generate_super_properties(self) -> str:
        """Generate X-Super-Properties header (base64 encoded client info)"""
        import base64
        
        super_properties = {
            'os': 'Windows',
            'browser': 'Discord Client',
            'release_channel': 'stable',
            'client_version': self.DISCORD_VERSIONS['client_version'],
            'os_version': '10.0.19045',
            'os_arch': 'x64',
            'system_locale': 'en-US',
            'client_build_number': int(self.DISCORD_VERSIONS['build_number']),
            'native_build_number': 36089,
            'client_event_source': None,
            'design_id': 0
        }
        
        json_str = json.dumps(super_properties, separators=(',', ':'))
        encoded = base64.b64encode(json_str.encode()).decode()
        return encoded
    
    def _handle_rate_limit(self, response: requests.Response, endpoint: str):
        """Handle Discord rate limits properly"""
        if response.status_code == 429:
            retry_after = response.json().get('retry_after', 5)
            logging.warning(f"[WARNING] Rate limited on {endpoint}. Waiting {retry_after}s")
            time.sleep(retry_after)
            return True
        
        if 'X-RateLimit-Remaining' in response.headers:
            remaining = int(response.headers.get('X-RateLimit-Remaining', 1))
            reset_timestamp = float(response.headers.get('X-RateLimit-Reset', 0))
            
            if remaining == 0:
                wait_time = max(0, reset_timestamp - time.time())
                logging.info(f"[INFO] Rate limit approaching. Waiting {wait_time:.2f}s")
                time.sleep(wait_time + 0.5)
        
        return False
    
    # ===========================
    # AMOUNT PARSING UTILITIES
    # ===========================
    
    @staticmethod
    def parse_amount(amount_value) -> int:
        """Parse amount value supporting scientific notation"""
        try:
            if isinstance(amount_value, (int, float)):
                return int(amount_value)
            
            if isinstance(amount_value, str):
                amount_value = amount_value.strip().lower()
                
                if 'e' in amount_value:
                    return int(float(amount_value))
                
                return int(float(amount_value))
            
            return int(amount_value)
            
        except (ValueError, TypeError) as e:
            logging.error(f"[PARSE] Failed to parse amount '{amount_value}': {e}")
            return 0
    
    @staticmethod
    def format_amount(amount: int) -> str:
        """Format amount with commas for display"""
        try:
            return f"{int(amount):,}"
        except:
            return str(amount)

    async def _async_unlock_sequence(
        self, 
        channel_id: str, 
        guild_id: str, 
        reason: str, 
        opening_message: str
    ) -> bool:
        """
        Async unlock sequence - runs in order:
        1. $reset-economy (BEFORE unlock)
        2. Wait 2 seconds  
        3. yes confirmation (BEFORE unlock)
        4. Wait 1 second
        5. Unlock channel
        6. Enable all features
        7. Send opening message
        
        Uses asyncio for non-blocking waits.
        """
        try:
            logging.info("[UNLOCK] 🚀 Starting unlock sequence...")
            logging.info("=" * 50)
            
            # Step 1: Send $reset-economy (BEFORE unlock)
            logging.info("[UNLOCK] 📤 Step 1/6: Sending $reset-economy...")
            await asyncio.to_thread(self.type_and_send, channel_id, "$reset-economy")
            
            # Step 2: Wait 2 seconds for bot confirmation prompt
            logging.info("[UNLOCK] ⏳ Step 2/6: Waiting 2 seconds for bot prompt...")
            await asyncio.sleep(2)
            
            # Step 3: Send yes confirmation (BEFORE unlock)
            logging.info("[UNLOCK] ✅ Step 3/6: Sending 'yes' confirmation...")
            await asyncio.to_thread(self.type_and_send, channel_id, "yes")
            
            # Wait for reset to complete
            logging.info("[UNLOCK] ⏳ Waiting 1 second for reset to complete...")
            await asyncio.sleep(1)
            
            # Step 4: NOW unlock the channel
            logging.info("[UNLOCK] 🔓 Step 4/6: Unlocking channel permissions...")
            success = await asyncio.to_thread(
                self.unlock_channel,
                channel_id,
                guild_id,
                reason
            )
            
            if not success:
                logging.error("[UNLOCK] ❌ Failed to unlock channel!")
                return False
            
            logging.info("[UNLOCK] ✅ Channel unlocked successfully!")
            
            # Step 5: Enable all features
            logging.info("[UNLOCK] 🔧 Step 5/6: Enabling all automated features...")
            await asyncio.to_thread(self.enable_all_features, True)
            self.log_feature_status()
            
            # Step 6: Send opening message
            logging.info("[UNLOCK] 📢 Step 6/6: Sending opening message...")
            await asyncio.to_thread(self.type_and_send, channel_id, opening_message)
            
            logging.info("=" * 50)
            logging.info("[UNLOCK] ✅ Unlock sequence completed successfully!")
            logging.info("=" * 50)
            return True
            
        except Exception as e:
            logging.error(f"[UNLOCK] ❌ Error in unlock sequence: {str(e)}")
            import traceback
            logging.error(traceback.format_exc())
            return False

    def _run_async_unlock_sequence(
        self, 
        channel_id: str, 
        guild_id: str, 
        reason: str, 
        opening_message: str
    ):
        """
        Wrapper to run async unlock sequence in a new event loop.
        Called from a background thread.
        """
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                self._async_unlock_sequence(channel_id, guild_id, reason, opening_message)
            )
            return result
        finally:
            loop.close()

    async def _async_lock_sequence(
        self, 
        channel_id: str, 
        guild_id: str, 
        reason: str, 
        closing_message: str
    ) -> bool:
        """
        Async lock sequence - runs in order:
        1. Lock channel
        2. Disable all features
        3. Send $lb
        4. Wait 5 seconds
        5. Send closing message
        """
        try:
            logging.info("[LOCK] 🚀 Starting lock sequence...")
            logging.info("=" * 50)
            
            # Step 1: Lock the channel
            logging.info("[LOCK] 🔒 Step 1/4: Locking channel permissions...")
            success = await asyncio.to_thread(
                self.lock_channel,
                channel_id,
                guild_id,
                reason
            )
            
            if not success:
                logging.error("[LOCK] ❌ Failed to lock channel!")
                return False
            
            logging.info("[LOCK] ✅ Channel locked successfully!")
            
            # Step 2: Disable all features
            logging.info("[LOCK] 🔧 Step 2/4: Disabling all automated features...")
            await asyncio.to_thread(self.disable_all_features, True)
            self.log_feature_status()
            
            # Step 3: Send $lb
            logging.info("[LOCK] 📤 Step 3/4: Sending $lb command...")
            await asyncio.to_thread(self.type_and_send, channel_id, "$lb")
            
            # Wait 5 seconds
            logging.info("[LOCK] ⏳ Waiting 5 seconds...")
            await asyncio.sleep(5)
            
            # Step 4: Send closing message
            logging.info("[LOCK] 📢 Step 4/4: Sending closing message...")
            await asyncio.to_thread(self.type_and_send, channel_id, closing_message)
            
            logging.info("=" * 50)
            logging.info("[LOCK] ✅ Lock sequence completed successfully!")
            logging.info("=" * 50)
            return True
            
        except Exception as e:
            logging.error(f"[LOCK] ❌ Error in lock sequence: {str(e)}")
            import traceback
            logging.error(traceback.format_exc())
            return False

    def _run_async_lock_sequence(
        self, 
        channel_id: str, 
        guild_id: str, 
        reason: str, 
        closing_message: str
    ):
        """
        Wrapper to run async lock sequence in a new event loop.
        Called from a background thread.
        """
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                self._async_lock_sequence(channel_id, guild_id, reason, closing_message)
            )
            return result
        finally:
            loop.close()
    
    # ===========================
    # TYPING INDICATOR FEATURE
    # ===========================
    
    def start_typing(self, channel_id: str) -> bool:
        """Send typing indicator to a Discord channel"""
        endpoint = f'{self.DISCORD_API_BASE}/channels/{channel_id}/typing'
        headers = self._get_discord_headers(self.discord_token)
        
        try:
            response = self.session.post(
                endpoint,
                headers=headers,
                timeout=10
            )
            
            if self._handle_rate_limit(response, endpoint):
                response = self.session.post(
                    endpoint,
                    headers=headers,
                    timeout=10
                )
            
            if response.status_code in [200, 204]:
                logging.debug(f"[TYPING] Started typing in channel {channel_id}")
                return True
            elif response.status_code == 403:
                logging.warning(f"[TYPING] Cannot send typing indicator - no permission in channel {channel_id}")
                return False
            elif response.status_code == 404:
                logging.error(f"[TYPING] Channel {channel_id} not found")
                return False
            else:
                logging.warning(f"[TYPING] Unexpected response {response.status_code}: {response.text}")
                return False
                
        except requests.exceptions.Timeout:
            logging.warning(f"[TYPING] Timeout sending typing indicator")
            return False
        except requests.exceptions.RequestException as e:
            logging.error(f"[TYPING] Error: {str(e)}")
            return False
    
    def type_and_send(
        self, 
        channel_id: str, 
        content: str, 
        typing_duration: float = None,
        min_typing: float = 1.0,
        max_typing: float = 3.0,
        **kwargs
    ) -> Optional[Dict]:
        """Send typing indicator, wait, then send message (more human-like)"""
        if typing_duration is None:
            chars_per_second = random.uniform(5, 8)
            calculated_duration = len(content) / chars_per_second
            typing_duration = max(min_typing, min(calculated_duration, max_typing))
            typing_duration += random.uniform(-0.3, 0.5)
            typing_duration = max(min_typing, typing_duration)
        
        logging.debug(f"[TYPING] Will type for {typing_duration:.2f}s before sending")
        
        self.start_typing(channel_id)
        
        remaining = typing_duration
        while remaining > 0:
            sleep_time = min(remaining, 8.0)
            time.sleep(sleep_time)
            remaining -= sleep_time
            
            if remaining > 0:
                self.start_typing(channel_id)
        
        return self.send_message(channel_id, content, **kwargs)
    
    def send_message(self, channel_id: str, content: str, **kwargs) -> Optional[Dict]:
        """Send a message to a Discord channel"""
        endpoint = f'{self.DISCORD_API_BASE}/channels/{channel_id}/messages'
        headers = self._get_discord_headers(self.discord_token)
        
        payload = {
            'content': content,
            **kwargs
        }
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                time.sleep(random.uniform(0.1, 0.5))
                
                response = self.session.post(
                    endpoint,
                    headers=headers,
                    json=payload,
                    timeout=15
                )
                
                if self._handle_rate_limit(response, endpoint):
                    continue
                
                if response.status_code == 200:
                    message_data = response.json()
                    logging.info(f"[SUCCESS] Message sent to channel {channel_id}")
                    logging.debug(f"Message ID: {message_data.get('id')}")
                    return message_data
                
                elif response.status_code == 401:
                    logging.error(f"[ERROR] Unauthorized - Invalid token")
                    return None
                
                elif response.status_code == 403:
                    logging.error(f"[ERROR] Forbidden - Cannot send messages to channel {channel_id}")
                    return None
                
                elif response.status_code == 404:
                    logging.error(f"[ERROR] Channel {channel_id} not found")
                    return None
                
                else:
                    logging.error(f"[ERROR] API Error {response.status_code}: {response.text}")
                    
                    if attempt < max_retries - 1:
                        wait_time = (2 ** attempt) + random.uniform(0, 1)
                        logging.info(f"Retrying in {wait_time:.2f}s...")
                        time.sleep(wait_time)
                        continue
                    
                    return None
                    
            except requests.exceptions.Timeout:
                logging.error(f"[ERROR] Request timeout (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                return None
                
            except requests.exceptions.RequestException as e:
                logging.error(f"[ERROR] Request exception: {str(e)}")
                return None
        
        return None
    
    def fetch_latest_messages(self, channel_id: str, limit: int = 5) -> Optional[list]:
        """Fetch latest messages from a channel"""
        endpoint = f'{self.DISCORD_API_BASE}/channels/{channel_id}/messages?limit={limit}'
        headers = self._get_discord_headers(self.discord_token)
        
        try:
            response = self.session.get(
                endpoint,
                headers=headers,
                timeout=15
            )
            
            if self._handle_rate_limit(response, endpoint):
                time.sleep(2)
                return self.fetch_latest_messages(channel_id, limit)
            
            if response.status_code == 200:
                messages = response.json()
                logging.debug(f"[FETCH] Retrieved {len(messages)} messages from channel {channel_id}")
                return messages
            else:
                logging.error(f"[FETCH] Failed to fetch messages: {response.status_code}")
                return None
                
        except Exception as e:
            logging.error(f"[FETCH] Error fetching messages: {str(e)}")
            return None
    
    def fetch_latest_bot_message(self, channel_id: str, bot_id: str = None) -> Optional[Dict]:
        """Fetch the latest message from a specific bot"""
        if bot_id is None:
            cash_check_config = self.config.get('cash_checks', {})
            bot_id = cash_check_config.get('bot_id', '292953664492929025')
        
        messages = self.fetch_latest_messages(channel_id, limit=10)
        
        if not messages:
            return None
        
        for msg in messages:
            if msg.get('author', {}).get('id') == bot_id:
                logging.debug(f"[FETCH] Found bot message: {msg.get('id')}")
                return msg
        
        logging.warning(f"[FETCH] No message from bot {bot_id} found in recent messages")
        return None
    
    def update_channel_permissions(
        self,
        channel_id: str,
        permissions: Dict[str, Any],
        reason: Optional[str] = None
    ) -> bool:
        """Update Discord channel permissions"""
        
        endpoint = f'{self.DISCORD_API_BASE}/channels/{channel_id}'
        headers = self._get_discord_headers(self.discord_token)
        
        if reason:
            headers['X-Audit-Log-Reason'] = reason
        
        payload = {
            'permission_overwrites': permissions.get('overwrites', [])
        }
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                time.sleep(random.uniform(0.1, 0.5))
                
                response = self.session.patch(
                    endpoint,
                    headers=headers,
                    json=payload,
                    timeout=15
                )
                
                if self._handle_rate_limit(response, endpoint):
                    continue
                
                if response.status_code in [200, 204]:
                    logging.info(f"[SUCCESS] Channel {channel_id} permissions updated successfully")
                    logging.debug(f"Response: {response.text}")
                    return True
                
                elif response.status_code == 401:
                    logging.error(f"[ERROR] Unauthorized - Invalid token")
                    return False
                
                elif response.status_code == 403:
                    logging.error(f"[ERROR] Forbidden - Insufficient permissions")
                    return False
                
                elif response.status_code == 404:
                    logging.error(f"[ERROR] Channel {channel_id} not found")
                    return False
                
                else:
                    logging.error(f"[ERROR] API Error {response.status_code}: {response.text}")
                    
                    if attempt < max_retries - 1:
                        wait_time = (2 ** attempt) + random.uniform(0, 1)
                        logging.info(f"Retrying in {wait_time:.2f}s...")
                        time.sleep(wait_time)
                        continue
                    
                    return False
                    
            except requests.exceptions.Timeout:
                logging.error(f"[ERROR] Request timeout (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                return False
                
            except requests.exceptions.RequestException as e:
                logging.error(f"[ERROR] Request exception: {str(e)}")
                return False
        
        return False
    
    def lock_channel(
        self,
        channel_id: str,
        guild_id: str,
        reason: str = "Scheduled channel lock"
    ) -> bool:
        """Lock a channel (deny SEND_MESSAGES for @everyone) - preserves other permissions"""
        
        endpoint = f'{self.DISCORD_API_BASE}/channels/{channel_id}/permissions/{guild_id}'
        headers = self._get_discord_headers(self.discord_token)
        
        if reason:
            headers['X-Audit-Log-Reason'] = reason
        
        payload = {
            'type': 0,  # 0 = role, 1 = member
            'deny': str(1 << 11),  # SEND_MESSAGES = 2048
        }
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                time.sleep(random.uniform(0.1, 0.5))
                
                response = self.session.put(  # ✅ PUT, not PATCH
                    endpoint,
                    headers=headers,
                    json=payload,
                    timeout=15
                )
                
                if self._handle_rate_limit(response, endpoint):
                    continue
                
                if response.status_code in [200, 204]:
                    logging.info(f"[SUCCESS] Channel {channel_id} LOCKED (preserved other permissions)")
                    return True
                
                elif response.status_code == 401:
                    logging.error(f"[ERROR] Unauthorized - Invalid token")
                    return False
                
                elif response.status_code == 403:
                    logging.error(f"[ERROR] Forbidden - Insufficient permissions")
                    return False
                
                elif response.status_code == 404:
                    logging.error(f"[ERROR] Channel {channel_id} not found")
                    return False
                
                else:
                    logging.error(f"[ERROR] API Error {response.status_code}: {response.text}")
                    
                    if attempt < max_retries - 1:
                        wait_time = (2 ** attempt) + random.uniform(0, 1)
                        logging.info(f"Retrying in {wait_time:.2f}s...")
                        time.sleep(wait_time)
                        continue
                    
                    return False
                    
            except requests.exceptions.Timeout:
                logging.error(f"[ERROR] Request timeout (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                return False
                
            except requests.exceptions.RequestException as e:
                logging.error(f"[ERROR] Request exception: {str(e)}")
                return False
        
        return False

    def unlock_channel(
        self,
        channel_id: str,
        guild_id: str,
        reason: str = "Scheduled channel unlock"
    ) -> bool:
        """Unlock a channel (allow SEND_MESSAGES for @everyone) - preserves other permissions"""
        
        endpoint = f'{self.DISCORD_API_BASE}/channels/{channel_id}/permissions/{guild_id}'
        headers = self._get_discord_headers(self.discord_token)
        
        if reason:
            headers['X-Audit-Log-Reason'] = reason
        
        payload = {
            'type': 0,  # 0 = role, 1 = member
            'allow': str(1 << 11),  # SEND_MESSAGES = 2048
        }
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                time.sleep(random.uniform(0.1, 0.5))
                
                response = self.session.put(  # ✅ PUT, not PATCH
                    endpoint,
                    headers=headers,
                    json=payload,
                    timeout=15
                )
                
                if self._handle_rate_limit(response, endpoint):
                    continue
                
                if response.status_code in [200, 204]:
                    logging.info(f"[SUCCESS] Channel {channel_id} UNLOCKED (preserved other permissions)")
                    return True
                
                elif response.status_code == 401:
                    logging.error(f"[ERROR] Unauthorized - Invalid token")
                    return False
                
                elif response.status_code == 403:
                    logging.error(f"[ERROR] Forbidden - Insufficient permissions")
                    return False
                
                elif response.status_code == 404:
                    logging.error(f"[ERROR] Channel {channel_id} not found")
                    return False
                
                else:
                    logging.error(f"[ERROR] API Error {response.status_code}: {response.text}")
                    
                    if attempt < max_retries - 1:
                        wait_time = (2 ** attempt) + random.uniform(0, 1)
                        logging.info(f"Retrying in {wait_time:.2f}s...")
                        time.sleep(wait_time)
                        continue
                    
                    return False
                    
            except requests.exceptions.Timeout:
                logging.error(f"[ERROR] Request timeout (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                return False
                
            except requests.exceptions.RequestException as e:
                logging.error(f"[ERROR] Request exception: {str(e)}")
                return False
        
        return False
    
    def parse_time_format(self, time_str: str) -> Dict[str, int]:
        """Parse time string formats"""
        time_str = time_str.strip().lower()
        
        weekdays = {
            'monday': 0, 'mon': 0,
            'tuesday': 1, 'tue': 1, 'tues': 1,
            'wednesday': 2, 'wed': 2,
            'thursday': 3, 'thu': 3, 'thur': 3, 'thurs': 3,
            'friday': 4, 'fri': 4,
            'saturday': 5, 'sat': 5,
            'sunday': 6, 'sun': 6
        }
        
        weekday = None
        time_part = time_str
        
        for day_name, day_num in weekdays.items():
            if time_str.startswith(day_name):
                weekday = day_num
                time_part = time_str.replace(day_name, '').strip()
                break
        
        time_patterns = [
            r'(\d{1,2}):(\d{2})\s*(am|pm)',
            r'(\d{1,2})\s*(am|pm)',
            r'(\d{1,2}):(\d{2})'
        ]
        
        for pattern in time_patterns:
            match = re.search(pattern, time_part)
            if match:
                groups = match.groups()
                
                if len(groups) == 2 and groups[1] in ['am', 'pm']:
                    hour = int(groups[0])
                    minute = 0
                    if groups[1] == 'pm' and hour != 12:
                        hour += 12
                    elif groups[1] == 'am' and hour == 12:
                        hour = 0
                        
                elif len(groups) == 3:
                    hour = int(groups[0])
                    minute = int(groups[1])
                    if groups[2] == 'pm' and hour != 12:
                        hour += 12
                    elif groups[2] == 'am' and hour == 12:
                        hour = 0
                        
                else:
                    hour = int(groups[0])
                    minute = int(groups[1])
                
                return {
                    'hour': hour,
                    'minute': minute,
                    'weekday': weekday
                }
        
        raise ValueError(f"Invalid time format: {time_str}")
    
    def should_execute(self, time_config: str, current_time: datetime) -> bool:
        """Check if current time matches configured time"""
        parsed = self.parse_time_format(time_config)
        
        if parsed['weekday'] is not None:
            if current_time.weekday() != parsed['weekday']:
                return False
        
        return (current_time.hour == parsed['hour'] and 
                current_time.minute == parsed['minute'])
    
    def has_auto_cash_time_passed(self, current_time: datetime = None) -> bool:
        """Check if the auto-cash scheduled time has passed for today"""
        if current_time is None:
            current_time = datetime.now(self.ist_tz)
        
        auto_cash_config = self.config.get('auto_cash', {})
        auto_cash_time = auto_cash_config.get('time', '12:00 AM')
        
        try:
            parsed_time = self.parse_time_format(auto_cash_time)
            auto_cash_hour = parsed_time['hour']
            auto_cash_minute = parsed_time['minute']
            
            auto_cash_passed = (
                current_time.hour > auto_cash_hour or 
                (current_time.hour == auto_cash_hour and current_time.minute >= auto_cash_minute)
            )
            
            return auto_cash_passed
            
        except Exception as e:
            logging.error(f"[TIME-CHECK] Failed to parse auto-cash time: {e}")
            return True
    
    def has_auto_cash_executed_today(self) -> bool:
        """Check if auto-cash has actually executed today"""
        current_time = datetime.now(self.ist_tz)
        today_key = current_time.strftime('%Y-%m-%d')
        
        return self.last_auto_cash_execution == today_key
    
    def execute_task(self, task_name: str, task_config: Dict):
        """
        Execute a scheduled task
        
        IMPORTANT:
        - On LOCK action: Locks channel, DISABLES all features, sends $lb and closing message
        - On UNLOCK action: Sends $reset-economy + yes FIRST, then unlocks, ENABLES features
        """
        current_time = datetime.now(self.ist_tz)
        execution_key = f"{task_name}_{current_time.strftime('%Y-%m-%d_%H:%M')}"
        
        if execution_key in self.last_execution:
            return
        
        if self.should_execute(task_config['lock_time'], current_time):
            logging.info("=" * 60)
            logging.info(f"[EXECUTE] [{current_time.strftime('%I:%M %p IST')}] Executing: {task_name}")
            logging.info("=" * 60)
            
            action = task_config.get('action', 'custom')
            message = task_config.get('message', '').strip()
            success = False
            
            if action == 'lock':
                # ========================================
                # LOCK ACTION - DISABLE ALL FEATURES
                # ========================================
                logging.info("[LOCK] 🔒 Initiating channel LOCK sequence...")
                
                # Get closing message
                if not message:
                    message = self.config.get('closing_message', 'Channel has been locked.').strip()
                    if not message:
                        message = 'Channel has been locked.'
                
                # Run lock sequence in background thread with asyncio
                thread = threading.Thread(
                    target=self._run_async_lock_sequence,
                    args=(
                        task_config['channel_id'],
                        task_config['guild_id'],
                        task_config.get('reason', 'Scheduled lock'),
                        message
                    )
                )
                thread.daemon = True
                thread.start()
                
                # Mark as successful - actual lock happens in thread
                success = True
            
            elif action == 'unlock':
                # ========================================
                # UNLOCK ACTION - RESET ECONOMY FIRST, THEN UNLOCK
                # ========================================
                logging.info("[UNLOCK] 🔓 Initiating channel UNLOCK sequence...")
                logging.info("[UNLOCK] 📋 Sequence: $reset-economy → yes → unlock → enable features → message")
                
                # Get opening message
                if not message:
                    message = self.config.get('opening_message', 'Channel has been unlocked.').strip()
                    if not message:
                        message = 'Channel has been unlocked.'
                
                # Run unlock sequence in background thread with asyncio:
                # $reset-economy -> 2s wait -> yes -> unlock -> enable features -> opening message
                thread = threading.Thread(
                    target=self._run_async_unlock_sequence,
                    args=(
                        task_config['channel_id'],
                        task_config['guild_id'],
                        task_config.get('reason', 'Scheduled unlock'),
                        message
                    )
                )
                thread.daemon = True
                thread.start()
                
                # Mark as successful - actual unlock happens in thread
                success = True
            
            else:
                # Custom action (no feature toggling)
                success = self.update_channel_permissions(
                    channel_id=task_config['channel_id'],
                    permissions=task_config['permissions'],
                    reason=task_config.get('reason')
                )
                if message and success:
                    self.type_and_send(task_config['channel_id'], message)
            
            if success:
                self.last_execution[execution_key] = current_time
                logging.info(f"[EXECUTE] ✅ Task '{task_name}' initiated successfully")
                
                # Clean up old executions
                if len(self.last_execution) > 1000:
                    oldest = min(self.last_execution.keys())
                    del self.last_execution[oldest]
            else:
                logging.error(f"[EXECUTE] ❌ Task '{task_name}' failed")
            
            logging.info("=" * 60)

    def _send_messages_with_typing(self, channel_id: str, messages: list, delay: int = 5):
        """Send multiple messages with typing indicator and delay"""
        for i, message in enumerate(messages):
            self.type_and_send(channel_id, message)
            
            if i < len(messages) - 1:
                time.sleep(delay)
    
    def _send_messages_delayed(self, channel_id: str, messages: list, delay: int = 5):
        """Send multiple messages with delay (legacy method)"""
        for i, message in enumerate(messages):
            self.send_message(channel_id, message)
            
            if i < len(messages) - 1:
                time.sleep(delay)
    
    # ===========================
    # AUTO-CASH FEATURE
    # ===========================
    
    def check_auto_cash(self):
        """Check and execute auto-cash if configured and enabled"""
        auto_cash_config = self.config.get('auto_cash', {})
        
        if not auto_cash_config.get('enabled', False):
            logging.debug("[AUTO-CASH] Feature is DISABLED, skipping...")
            return
        
        current_time = datetime.now(self.ist_tz)
        execution_key = current_time.strftime('%Y-%m-%d')
        
        if self.last_auto_cash_execution == execution_key:
            return
        
        time_config = auto_cash_config.get('time', '12:00 AM')
        channel_id = auto_cash_config.get('channel_id')
        amounts = auto_cash_config.get('amounts', {})
        command_template = auto_cash_config.get('command_template', '$add-cash {amount}')
        
        if not channel_id:
            logging.error("[AUTO-CASH] Channel ID not configured!")
            return
        
        if not self.should_execute(time_config, current_time):
            return
        
        weekday_name = self.WEEKDAYS[current_time.weekday()]
        amount = amounts.get(weekday_name)
        
        if not amount:
            logging.warning(f"[AUTO-CASH] No amount configured for {weekday_name}")
            return
        
        amount_int = self.parse_amount(amount)
        command = command_template.format(amount=amount_int)
        
        logging.info("=" * 60)
        logging.info(f"[AUTO-CASH] Executing auto-cash for {weekday_name}")
        logging.info(f"[AUTO-CASH] Amount: {self.format_amount(amount_int)} (config: {amount})")
        logging.info(f"[AUTO-CASH] Command: {command}")
        logging.info("=" * 60)
        
        result = self.type_and_send(channel_id, command)
        
        if result:
            self.last_auto_cash_execution = execution_key
            logging.info(f"[AUTO-CASH] [OK] Successfully executed for {weekday_name}")
        else:
            logging.error(f"[AUTO-CASH] [ERROR] Failed to execute for {weekday_name}")
    
    def test_auto_cash_all_days(self):
        """Test auto-cash for all weekdays"""
        auto_cash_config = self.config.get('auto_cash', {})
        
        if not auto_cash_config.get('enabled', False):
            logging.error("[TEST] Auto-cash is not enabled in config!")
            return
        
        channel_id = auto_cash_config.get('channel_id')
        amounts = auto_cash_config.get('amounts', {})
        command_template = auto_cash_config.get('command_template', '$add-cash {amount}')
        
        if not channel_id:
            logging.error("[TEST] Channel ID not configured!")
            return
        
        logging.info("=" * 60)
        logging.info("[TEST] TESTING AUTO-CASH FOR ALL WEEKDAYS")
        logging.info("=" * 60)
        
        for weekday_name in self.WEEKDAYS:
            amount = amounts.get(weekday_name)
            
            if not amount:
                logging.warning(f"[TEST] No amount configured for {weekday_name}")
                continue
            
            amount_int = self.parse_amount(amount)
            command = command_template.format(amount=amount_int)
            
            logging.info(f"\n[TEST] Testing {weekday_name}:")
            logging.info(f"  [CASH] Amount: {self.format_amount(amount_int)} (config: {amount})")
            logging.info(f"  [CMD] Command: {command}")
            
            result = self.type_and_send(channel_id, command)
            
            if result:
                logging.info(f"  [OK] SUCCESS - {weekday_name} test passed")
            else:
                logging.error(f"  [X] FAILED - {weekday_name} test failed")
            
            time.sleep(2)
        
        logging.info("\n" + "=" * 60)
        logging.info("[TEST] ALL WEEKDAY TESTS COMPLETED")
        logging.info("=" * 60)

    def test_auto_cash_single_day(self, weekday_name: str):
        """Test auto-cash for a specific weekday"""
        auto_cash_config = self.config.get('auto_cash', {})
        
        if not auto_cash_config.get('enabled', False):
            logging.error("[TEST] Auto-cash is not enabled in config!")
            return False
        
        channel_id = auto_cash_config.get('channel_id')
        amounts = auto_cash_config.get('amounts', {})
        command_template = auto_cash_config.get('command_template', '$add-cash {amount}')
        
        amount = amounts.get(weekday_name)
        
        if not amount:
            logging.error(f"[TEST] No amount configured for {weekday_name}")
            return False
        
        amount_int = self.parse_amount(amount)
        command = command_template.format(amount=amount_int)
        
        logging.info("=" * 60)
        logging.info(f"[TEST] Testing {weekday_name}")
        logging.info(f"  [CASH] Amount: {self.format_amount(amount_int)} (config: {amount})")
        logging.info(f"  [CMD] Command: {command}")
        logging.info("=" * 60)
        
        result = self.type_and_send(channel_id, command)
        
        if result:
            logging.info(f"[TEST] [OK] {weekday_name} test PASSED")
            return True
        else:
            logging.error(f"[TEST] [X] {weekday_name} test FAILED")
            return False

    def simulate_weekday_execution(self, weekday_name: str):
        """Simulate auto-cash execution for a specific weekday"""
        auto_cash_config = self.config.get('auto_cash', {})
        
        if not auto_cash_config.get('enabled', False):
            logging.error("[SIMULATE] Auto-cash is not enabled!")
            return False
        
        channel_id = auto_cash_config.get('channel_id')
        amounts = auto_cash_config.get('amounts', {})
        command_template = auto_cash_config.get('command_template', '$add-cash {amount}')
        
        amount = amounts.get(weekday_name)
        
        if not amount:
            logging.warning(f"[SIMULATE] No amount for {weekday_name}")
            return False
        
        amount_int = self.parse_amount(amount)
        command = command_template.format(amount=amount_int)
        
        logging.info(f"[SIMULATE] Executing for {weekday_name}: {command}")
        
        result = self.type_and_send(channel_id, command)
        
        if result:
            logging.info(f"[SIMULATE] [OK] {weekday_name} executed successfully")
            return True
        else:
            logging.error(f"[SIMULATE] [X] {weekday_name} failed")
            return False

    # ===========================
    # CASH CHECK FEATURE
    # ===========================
    
    def parse_lb_cash_response(self, message_data: Dict) -> Optional[int]:
        """Parse $lb -cash response to extract top user's cash amount"""
        try:
            embeds = message_data.get('embeds', [])
            if not embeds:
                logging.error("[CASH-CHECK] No embeds in response")
                return None
            
            embed = embeds[0]
            description = embed.get('description', '')
            
            logging.info(f"[CASH-CHECK] Description length: {len(description)} chars")
            logging.debug(f"[CASH-CHECK] Description repr: {repr(description[:500])}")
            
            if not description:
                logging.error("[CASH-CHECK] Empty description in embed")
                return None
            
            lines = description.split('\n')
            logging.info(f"[CASH-CHECK] Number of lines in embed: {len(lines)}")
            
            for i, line in enumerate(lines):
                line_stripped = line.strip()
                
                if not line_stripped:
                    continue
                
                if i < 5:
                    logging.debug(f"[CASH-CHECK] Line {i}: {line_stripped[:80]}...")
                
                is_first = any([
                    line_stripped.startswith('**1.**'),
                    line_stripped.startswith('**1**'),
                    line_stripped.startswith('1.'),
                    line_stripped.startswith('1)'),
                    '**1.**' in line_stripped,
                    '**1**.' in line_stripped,
                    re.match(r'^\*?\*?1[\.\)\:]', line_stripped),
                ])
                
                if not is_first:
                    continue
                
                logging.info(f"[CASH-CHECK] Found rank 1 line: {line_stripped}")
                
                number_pattern = r'(\d{1,3}(?:,\d{3})*|\d{4,})'
                matches = re.findall(number_pattern, line_stripped)
                
                logging.debug(f"[CASH-CHECK] Numbers found in line: {matches}")
                
                amounts = []
                for match in matches:
                    clean = match.replace(',', '')
                    if clean.isdigit() and len(clean) >= 4:
                        amounts.append(int(clean))
                
                if amounts:
                    amount = max(amounts)
                    logging.info(f"[CASH-CHECK] ✓ Top user cash amount: {self.format_amount(amount)}")
                    return amount
            
            logging.warning("[CASH-CHECK] Primary parsing failed, trying fallback method...")
            
            number_pattern = r'(\d{1,3}(?:,\d{3})+|\d{6,})'
            all_matches = re.findall(number_pattern, description)
            
            logging.debug(f"[CASH-CHECK] All large numbers found: {all_matches[:10]}")
            
            if all_matches:
                amounts = []
                for match in all_matches:
                    clean = match.replace(',', '')
                    if clean.isdigit():
                        amounts.append(int(clean))
                
                if amounts:
                    amounts.sort(reverse=True)
                    amount = amounts[0]
                    logging.info(f"[CASH-CHECK] ✓ Top user cash (fallback): {self.format_amount(amount)}")
                    return amount
            
            logging.error("[CASH-CHECK] No valid cash amounts found in embed")
            logging.error(f"[CASH-CHECK] Description preview: {description[:300]}")
            return None
            
        except Exception as e:
            logging.error(f"[CASH-CHECK] Parse error: {str(e)}")
            import traceback
            logging.error(traceback.format_exc())
            return None
    
    def calculate_cumulative_limit(self) -> int:
        """Calculate cumulative cash limit based on current weekday and time"""
        auto_cash_config = self.config.get('auto_cash', {})
        amounts = auto_cash_config.get('amounts', {})
        
        weekday_order = list(amounts.keys())
        
        if not weekday_order:
            logging.error("[CASH-CHECK] No amounts configured!")
            return 0
        
        current_time = datetime.now(self.ist_tz)
        current_day_name = self.WEEKDAYS[current_time.weekday()]
        
        auto_cash_time_passed = self.has_auto_cash_time_passed(current_time)
        auto_cash_executed_today = self.has_auto_cash_executed_today()
        
        logging.info(f"[CASH-CHECK] Current day: {current_day_name}")
        logging.info(f"[CASH-CHECK] Auto-cash time passed: {auto_cash_time_passed}")
        logging.info(f"[CASH-CHECK] Auto-cash executed today: {auto_cash_executed_today}")
        
        try:
            current_position = weekday_order.index(current_day_name)
        except ValueError:
            logging.error(f"[CASH-CHECK] Current day '{current_day_name}' not found in config!")
            return 0
        
        include_today = auto_cash_time_passed and auto_cash_executed_today
        
        if include_today:
            effective_position = current_position
            logging.info(f"[CASH-CHECK] ✓ Including today's amount (auto-cash executed)")
        else:
            effective_position = current_position - 1
            if not auto_cash_time_passed:
                logging.info(f"[CASH-CHECK] ✗ Excluding today - auto-cash time not reached yet")
            elif not auto_cash_executed_today:
                logging.info(f"[CASH-CHECK] ✗ Excluding today - auto-cash hasn't executed yet")
            
            if effective_position < 0:
                logging.info("[CASH-CHECK] First day of week cycle, auto-cash not yet run")
                logging.info("[CASH-CHECK] Returning 0 as limit (fresh week start)")
                return 0
        
        logging.debug(f"[CASH-CHECK] Config order: {weekday_order}")
        logging.debug(f"[CASH-CHECK] Current position: {current_position}, Effective position: {effective_position}")
        
        cumulative = 0
        for i in range(effective_position + 1):
            day_name = weekday_order[i]
            amount = self.parse_amount(amounts.get(day_name, 0))
            cumulative += amount
            logging.debug(f"[CASH-CHECK] Day {i+1}: {day_name} = {self.format_amount(amount)} (cumulative: {self.format_amount(cumulative)})")
        
        logging.info(f"[CASH-CHECK] Total cumulative limit: {self.format_amount(cumulative)}")
        return cumulative
    
    def check_cash_limit(self):
        """Check if top user's cash is below the cumulative limit and add if needed"""
        cash_check_config = self.config.get('cash_checks', {})
        auto_cash_config = self.config.get('auto_cash', {})
        
        if not cash_check_config.get('enabled', False):
            logging.debug("[CASH-CHECK] Feature is DISABLED, skipping...")
            return
        
        channel_id = cash_check_config.get('channel_id')
        command_template = cash_check_config.get('command', '$add-cash {amount}')
        
        if not channel_id:
            logging.error("[CASH-CHECK] Channel ID not configured")
            return
        
        current_time = datetime.now(self.ist_tz)
        current_day_name = self.WEEKDAYS[current_time.weekday()]
        
        auto_cash_time_passed = self.has_auto_cash_time_passed(current_time)
        auto_cash_executed_today = self.has_auto_cash_executed_today()
        
        logging.info("=" * 60)
        logging.info(f"[CASH-CHECK] Starting cash limit check")
        logging.info(f"[CASH-CHECK] Current time: {current_time.strftime('%I:%M %p IST')} ({current_day_name})")
        logging.info(f"[CASH-CHECK] Auto-cash time passed: {auto_cash_time_passed}")
        logging.info(f"[CASH-CHECK] Auto-cash executed today: {auto_cash_executed_today}")
        logging.info("=" * 60)
        
        if auto_cash_time_passed and not auto_cash_executed_today:
            logging.warning(f"[CASH-CHECK] ⚠️ Auto-cash time passed but hasn't executed today!")
            logging.warning(f"[CASH-CHECK] Will use previous day's cumulative limit")
        
        logging.info("[CASH-CHECK] Sending $lb -cash command...")
        lb_response = self.type_and_send(channel_id, "$lb -cash")
        
        if not lb_response:
            logging.error("[CASH-CHECK] Failed to send $lb -cash command")
            return
        
        logging.info("[CASH-CHECK] Waiting for bot response...")
        time.sleep(4)
        
        bot_message = self.fetch_latest_bot_message(channel_id)
        
        if not bot_message:
            logging.error("[CASH-CHECK] Could not fetch bot response")
            return
        
        current_amount = self.parse_lb_cash_response(bot_message)
        
        if current_amount is None:
            logging.error("[CASH-CHECK] Failed to parse cash amount from leaderboard")
            return
        
        limit = self.calculate_cumulative_limit()
        
        logging.info(f"[CASH-CHECK] Current amount: {self.format_amount(current_amount)}")
        logging.info(f"[CASH-CHECK] Required limit: {self.format_amount(limit)}")
        
        if current_amount < limit:
            difference = limit - current_amount
            
            logging.info("=" * 60)
            logging.info(f"[CASH-CHECK] ⚠️  BELOW LIMIT DETECTED!")
            logging.info(f"[CASH-CHECK] Current amount: {self.format_amount(current_amount)}")
            logging.info(f"[CASH-CHECK] Required limit: {self.format_amount(limit)}")
            logging.info(f"[CASH-CHECK] Difference: {self.format_amount(difference)}")
            logging.info("=" * 60)
            
            command = command_template.format(amount=difference)
            
            logging.info(f"[CASH-CHECK] Sending command: {command}")
            
            add_channel_id = auto_cash_config.get('channel_id', channel_id)
            result = self.type_and_send(add_channel_id, command)
            
            if result:
                logging.info(f"[CASH-CHECK] ✅ Successfully sent command to add {self.format_amount(difference)} cash")
            else:
                logging.error(f"[CASH-CHECK] ❌ Failed to send command")
        else:
            logging.info(f"[CASH-CHECK] ✅ OK - Current ({self.format_amount(current_amount)}) >= Limit ({self.format_amount(limit)})")
    
    def check_cash_checks_schedule(self):
        """Check if it's time to run cash checks based on interval"""
        cash_check_config = self.config.get('cash_checks', {})
        
        if not cash_check_config.get('enabled', False):
            return
        
        interval_minutes = cash_check_config.get('check_interval_minutes', 5)
        current_time = datetime.now(self.ist_tz)
        
        if self.last_cash_check_time is None:
            should_check = True
        else:
            time_diff = (current_time - self.last_cash_check_time).total_seconds() / 60
            should_check = time_diff >= interval_minutes
        
        if should_check:
            logging.info(f"[CASH-CHECK] Running periodic check (interval: {interval_minutes} min)")
            self.check_cash_limit()
            self.last_cash_check_time = current_time

    def test_cash_check(self):
        """Test cash check feature immediately"""
        logging.info("=" * 60)
        logging.info("[TEST] TESTING CASH CHECK FEATURE")
        logging.info("=" * 60)
        
        self.check_cash_limit()
        
        logging.info("=" * 60)
        logging.info("[TEST] CASH CHECK TEST COMPLETED")
        logging.info("=" * 60)

    def test_cumulative_calculation(self):
        """Test the cumulative limit calculation for debugging"""
        auto_cash_config = self.config.get('auto_cash', {})
        amounts = auto_cash_config.get('amounts', {})
        weekday_order = list(amounts.keys())
        
        current_time = datetime.now(self.ist_tz)
        current_day_name = self.WEEKDAYS[current_time.weekday()]
        
        logging.info("=" * 60)
        logging.info("[TEST] CUMULATIVE LIMIT CALCULATION TEST")
        logging.info("=" * 60)
        logging.info(f"Current day: {current_day_name}")
        logging.info(f"Current time: {current_time.strftime('%I:%M %p IST')}")
        logging.info(f"Auto-cash time: {auto_cash_config.get('time', 'Not set')}")
        logging.info(f"Auto-cash time passed: {self.has_auto_cash_time_passed()}")
        logging.info(f"Auto-cash executed today: {self.has_auto_cash_executed_today()}")
        logging.info(f"Last auto-cash execution: {self.last_auto_cash_execution}")
        logging.info("-" * 60)
        logging.info("Weekday order in config:")
        
        cumulative = 0
        for i, day in enumerate(weekday_order):
            amount = self.parse_amount(amounts.get(day, 0))
            cumulative += amount
            logging.info(f"  {i+1}. {day}: {self.format_amount(amount)} (cumulative: {self.format_amount(cumulative)})")
        
        logging.info("-" * 60)
        logging.info(f"Calculated limit (actual): {self.format_amount(self.calculate_cumulative_limit())}")
        logging.info("=" * 60)
    
    def test_typing(self, channel_id: str = None):
        """Test the typing indicator feature"""
        if channel_id is None:
            channel_id = self.config.get('auto_cash', {}).get('channel_id')
        
        if not channel_id:
            logging.error("[TEST] No channel ID available for typing test!")
            return
        
        logging.info("=" * 60)
        logging.info("[TEST] TESTING TYPING INDICATOR")
        logging.info(f"[TEST] Channel: {channel_id}")
        logging.info("=" * 60)
        
        logging.info("[TEST] Test 1: Basic typing indicator...")
        result = self.start_typing(channel_id)
        logging.info(f"[TEST] Typing indicator result: {'SUCCESS' if result else 'FAILED'}")
        
        time.sleep(2)
        
        logging.info("[TEST] Test 2: Type and send message...")
        result = self.type_and_send(channel_id, "Testing typing indicator! 🎯")
        logging.info(f"[TEST] Type and send result: {'SUCCESS' if result else 'FAILED'}")
        
        logging.info("=" * 60)
        logging.info("[TEST] TYPING TEST COMPLETED")
        logging.info("=" * 60)

    # ===========================
    # ADD CASH TO ROLES FEATURE
    # ===========================
    
    def add_cash_to_single_role(
        self, 
        role_name: str, 
        role_id: str, 
        amount, 
        channel_id: str, 
        command_template: str
    ) -> bool:
        """Add cash to a single role"""
        try:
            amount_int = self.parse_amount(amount)
            
            if amount_int <= 0:
                logging.error(f"[ROLE-CASH] Invalid amount for role '{role_name}': {amount}")
                return False
            
            command = command_template.replace('<@&ROLEID>', f'<@&{role_id}>')
            command = command.replace('ROLEID', role_id)
            command = command.replace('{amount}', str(amount_int))
            
            logging.info(f"[ROLE-CASH] Adding {self.format_amount(amount_int)} to role '{role_name}' (ID: {role_id})")
            logging.debug(f"[ROLE-CASH] Command: {command}")
            
            result = self.type_and_send(channel_id, command)
            
            if result:
                logging.info(f"[ROLE-CASH] ✅ Successfully added {self.format_amount(amount_int)} to role '{role_name}'")
                return True
            else:
                logging.error(f"[ROLE-CASH] ❌ Failed to add cash to role '{role_name}'")
                return False
                
        except Exception as e:
            logging.error(f"[ROLE-CASH] Error adding cash to role '{role_name}': {str(e)}")
            return False
    
    def add_cash_to_all_roles(self) -> Dict[str, bool]:
        """Add cash to all configured roles"""
        role_cash_config = self.config.get('add_cash_to_roles', {})
        
        if not role_cash_config.get('enabled', False):
            logging.debug("[ROLE-CASH] Feature is DISABLED, skipping...")
            return {}
        
        channel_id = role_cash_config.get('channel_id')
        command_template = role_cash_config.get('command', '$add-money-role cash <@&ROLEID> {amount}')
        roles = role_cash_config.get('roles', {})
        
        if not channel_id:
            logging.error("[ROLE-CASH] Channel ID not configured!")
            return {}
        
        if not roles:
            logging.warning("[ROLE-CASH] No roles configured!")
            return {}
        
        logging.info("=" * 60)
        logging.info(f"[ROLE-CASH] 💰 Starting cash distribution to {len(roles)} role(s)")
        logging.info(f"[ROLE-CASH] Channel: {channel_id}")
        logging.info(f"[ROLE-CASH] Command template: {command_template}")
        logging.info("=" * 60)
        
        results = {}
        success_count = 0
        fail_count = 0
        total_distributed = 0
        
        for role_name, role_data in roles.items():
            if not isinstance(role_data, dict):
                logging.error(f"[ROLE-CASH] Invalid config for role '{role_name}': expected dict, got {type(role_data)}")
                results[role_name] = False
                fail_count += 1
                continue
            
            for role_id, amount in role_data.items():
                role_id = str(role_id)
                amount_int = self.parse_amount(amount)
                
                logging.info(f"\n[ROLE-CASH] Processing: {role_name}")
                logging.info(f"  [ID] Role ID: {role_id}")
                logging.info(f"  [💰] Amount: {self.format_amount(amount_int)} (config: {amount})")
                
                success = self.add_cash_to_single_role(
                    role_name=role_name,
                    role_id=role_id,
                    amount=amount,
                    channel_id=channel_id,
                    command_template=command_template
                )
                
                results[role_name] = success
                
                if success:
                    success_count += 1
                    total_distributed += amount_int
                else:
                    fail_count += 1
                
                delay = random.uniform(2, 4)
                logging.debug(f"[ROLE-CASH] Waiting {delay:.1f}s before next role...")
                time.sleep(delay)
                
                break
        
        logging.info("\n" + "=" * 60)
        logging.info(f"[ROLE-CASH] 📊 Distribution Summary")
        logging.info(f"[ROLE-CASH] ✅ Success: {success_count}/{len(roles)}")
        logging.info(f"[ROLE-CASH] ❌ Failed: {fail_count}/{len(roles)}")
        logging.info(f"[ROLE-CASH] 💰 Total distributed: {self.format_amount(total_distributed)}")
        logging.info("=" * 60)
        
        return results
    
    def check_role_cash_schedule(self):
        """Check if it's time to run role cash distribution based on interval"""
        role_cash_config = self.config.get('add_cash_to_roles', {})
        
        if not role_cash_config.get('enabled', False):
            return
        
        interval_minutes = role_cash_config.get('check_interval_minutes', 30)
        current_time = datetime.now(self.ist_tz)
        
        if self.last_role_cash_time is None:
            should_run = True
            logging.info(f"[ROLE-CASH] First run - executing immediately")
        else:
            time_diff = (current_time - self.last_role_cash_time).total_seconds() / 60
            should_run = time_diff >= interval_minutes
            
            if not should_run:
                remaining = interval_minutes - time_diff
                logging.debug(f"[ROLE-CASH] Next run in {remaining:.1f} minutes")
        
        if should_run:
            logging.info(f"[ROLE-CASH] ⏰ Running scheduled distribution (interval: {interval_minutes} min)")
            
            self.add_cash_to_all_roles()
            
            self.last_role_cash_time = current_time
            
            next_run = current_time + timedelta(minutes=interval_minutes)
            logging.info(f"[ROLE-CASH] Next scheduled run: {next_run.strftime('%I:%M %p IST')}")
    
    def get_role_cash_status(self) -> Dict[str, Any]:
        """Get current status of role cash distribution feature"""
        role_cash_config = self.config.get('add_cash_to_roles', {})
        current_time = datetime.now(self.ist_tz)
        
        status = {
            'enabled': role_cash_config.get('enabled', False),
            'channel_id': role_cash_config.get('channel_id'),
            'interval_minutes': role_cash_config.get('check_interval_minutes', 30),
            'roles_count': len(role_cash_config.get('roles', {})),
            'last_execution': self.last_role_cash_time,
            'next_execution': None,
            'time_until_next': None
        }
        
        if self.last_role_cash_time and status['enabled']:
            interval = status['interval_minutes']
            next_exec = self.last_role_cash_time + timedelta(minutes=interval)
            status['next_execution'] = next_exec
            
            time_until = (next_exec - current_time).total_seconds() / 60
            status['time_until_next'] = max(0, time_until)
        
        return status
    
    def list_configured_roles(self):
        """List all configured roles and their amounts"""
        role_cash_config = self.config.get('add_cash_to_roles', {})
        
        logging.info("=" * 60)
        logging.info("[ROLE-CASH] 📋 CONFIGURED ROLES")
        logging.info("=" * 60)
        
        enabled = role_cash_config.get('enabled', False)
        logging.info(f"[STATUS] Feature: {'✅ ENABLED' if enabled else '❌ DISABLED'}")
        logging.info(f"[CONFIG] Channel ID: {role_cash_config.get('channel_id', 'Not set')}")
        logging.info(f"[CONFIG] Interval: {role_cash_config.get('check_interval_minutes', 30)} minutes")
        logging.info(f"[CONFIG] Command: {role_cash_config.get('command', 'Not set')}")
        
        if self.last_role_cash_time:
            logging.info(f"[TIME] Last run: {self.last_role_cash_time.strftime('%Y-%m-%d %I:%M %p IST')}")
        else:
            logging.info(f"[TIME] Last run: Never")
        
        logging.info("-" * 60)
        
        roles = role_cash_config.get('roles', {})
        
        if not roles:
            logging.info("[INFO] No roles configured!")
        else:
            logging.info(f"[INFO] {len(roles)} role(s) configured:\n")
            
            total_per_interval = 0
            
            for role_name, role_data in roles.items():
                if isinstance(role_data, dict):
                    for role_id, amount in role_data.items():
                        amount_int = self.parse_amount(amount)
                        total_per_interval += amount_int
                        
                        logging.info(f"  📌 {role_name}")
                        logging.info(f"     Role ID: {role_id}")
                        logging.info(f"     Amount: {self.format_amount(amount_int)} (config: {amount})")
                        logging.info("")
            
            logging.info("-" * 60)
            logging.info(f"[TOTAL] Per interval: {self.format_amount(total_per_interval)}")
            
            interval = role_cash_config.get('check_interval_minutes', 30)
            runs_per_hour = 60 / interval
            runs_per_day = 24 * runs_per_hour
            
            logging.info(f"[TOTAL] Per hour (~{runs_per_hour:.1f} runs): {self.format_amount(int(total_per_interval * runs_per_hour))}")
            logging.info(f"[TOTAL] Per day (~{runs_per_day:.0f} runs): {self.format_amount(int(total_per_interval * runs_per_day))}")
        
        logging.info("=" * 60)
    
    def test_role_cash_single(self, role_name: str) -> bool:
        """Test cash distribution for a single role"""
        role_cash_config = self.config.get('add_cash_to_roles', {})
        
        if not role_cash_config.get('enabled', False):
            logging.error("[TEST] add_cash_to_roles feature is DISABLED!")
            return False
        
        channel_id = role_cash_config.get('channel_id')
        command_template = role_cash_config.get('command', '$add-money-role cash <@&ROLEID> {amount}')
        roles = role_cash_config.get('roles', {})
        
        if role_name not in roles:
            logging.error(f"[TEST] Role '{role_name}' not found in config!")
            logging.info(f"[TEST] Available roles: {list(roles.keys())}")
            return False
        
        role_data = roles[role_name]
        
        if not isinstance(role_data, dict):
            logging.error(f"[TEST] Invalid config for role '{role_name}'")
            return False
        
        for role_id, amount in role_data.items():
            role_id = str(role_id)
            amount_int = self.parse_amount(amount)
            
            logging.info("=" * 60)
            logging.info(f"[TEST] Testing single role: {role_name}")
            logging.info(f"[TEST] Role ID: {role_id}")
            logging.info(f"[TEST] Amount: {self.format_amount(amount_int)} (config: {amount})")
            logging.info(f"[TEST] Channel: {channel_id}")
            logging.info("=" * 60)
            
            result = self.add_cash_to_single_role(
                role_name=role_name,
                role_id=role_id,
                amount=amount,
                channel_id=channel_id,
                command_template=command_template
            )
            
            logging.info("=" * 60)
            logging.info(f"[TEST] Result: {'✅ SUCCESS' if result else '❌ FAILED'}")
            logging.info("=" * 60)
            
            return result
        
        return False
    
    def test_role_cash_all(self) -> Dict[str, bool]:
        """Test cash distribution for ALL roles immediately"""
        logging.info("=" * 60)
        logging.info("[TEST] 🧪 TESTING ROLE CASH FOR ALL ROLES")
        logging.info("[TEST] This will send commands for ALL configured roles!")
        logging.info("=" * 60)
        
        results = self.add_cash_to_all_roles()
        
        logging.info("\n" + "=" * 60)
        logging.info("[TEST] 📊 TEST RESULTS SUMMARY")
        logging.info("-" * 60)
        
        for role_name, success in results.items():
            status = "✅ PASS" if success else "❌ FAIL"
            logging.info(f"  {role_name}: {status}")
        
        total = len(results)
        passed = sum(1 for s in results.values() if s)
        
        logging.info("-" * 60)
        logging.info(f"[TEST] Total: {passed}/{total} passed")
        logging.info("=" * 60)
        
        return results
    
    def test_role_cash_dry_run(self):
        """Dry run - shows what commands WOULD be sent without actually sending them"""
        role_cash_config = self.config.get('add_cash_to_roles', {})
        
        logging.info("=" * 60)
        logging.info("[DRY-RUN] 🔍 ROLE CASH DRY RUN (NO COMMANDS SENT)")
        logging.info("=" * 60)
        
        if not role_cash_config.get('enabled', False):
            logging.warning("[DRY-RUN] Feature is DISABLED")
        
        channel_id = role_cash_config.get('channel_id', 'NOT SET')
        command_template = role_cash_config.get('command', '$add-money-role cash <@&ROLEID> {amount}')
        roles = role_cash_config.get('roles', {})
        
        logging.info(f"[DRY-RUN] Channel: {channel_id}")
        logging.info(f"[DRY-RUN] Template: {command_template}")
        logging.info(f"[DRY-RUN] Roles to process: {len(roles)}")
        logging.info("-" * 60)
        
        total_amount = 0
        
        for role_name, role_data in roles.items():
            if isinstance(role_data, dict):
                for role_id, amount in role_data.items():
                    amount_int = self.parse_amount(amount)
                    total_amount += amount_int
                    
                    command = command_template.replace('<@&ROLEID>', f'<@&{role_id}>')
                    command = command.replace('ROLEID', str(role_id))
                    command = command.replace('{amount}', str(amount_int))
                    
                    logging.info(f"\n[DRY-RUN] Role: {role_name}")
                    logging.info(f"[DRY-RUN] Role ID: {role_id}")
                    logging.info(f"[DRY-RUN] Amount: {self.format_amount(amount_int)} (config: {amount})")
                    logging.info(f"[DRY-RUN] Command that would be sent:")
                    logging.info(f"[DRY-RUN] >>> {command}")
        
        logging.info("\n" + "-" * 60)
        logging.info(f"[DRY-RUN] Total amount per interval: {self.format_amount(total_amount)}")
        logging.info("=" * 60)
        logging.info("[DRY-RUN] Dry run complete - no commands were sent")
        logging.info("=" * 60)

    # ===========================
    # FEATURE TOGGLE TESTS
    # ===========================
    
    def test_feature_toggle(self):
        """Test enabling/disabling features without lock/unlock"""
        logging.info("=" * 60)
        logging.info("[TEST] TESTING FEATURE TOGGLE")
        logging.info("=" * 60)
        
        logging.info("\n[TEST] Current feature states:")
        self.log_feature_status()
        
        logging.info("\n[TEST] Disabling all features...")
        self.disable_all_features(save=False)  # Don't save during test
        
        logging.info("\n[TEST] After disable:")
        self.log_feature_status()
        
        time.sleep(2)
        
        logging.info("\n[TEST] Enabling all features...")
        self.enable_all_features(save=False)  # Don't save during test
        
        logging.info("\n[TEST] After enable:")
        self.log_feature_status()
        
        logging.info("=" * 60)
        logging.info("[TEST] FEATURE TOGGLE TEST COMPLETE")
        logging.info("[TEST] Note: Changes were NOT saved to config file")
        logging.info("=" * 60)
    
    def test_lock_with_feature_toggle(self, channel_id: str = None, guild_id: str = None):
        """Test lock action with feature toggling (simulated)"""
        if not channel_id:
            tasks = self.config.get('tasks', {})
            for task_name, task_config in tasks.items():
                if task_config.get('action') == 'lock':
                    channel_id = task_config.get('channel_id')
                    guild_id = task_config.get('guild_id')
                    break
        
        if not channel_id or not guild_id:
            logging.error("[TEST] No lock task found in config and no IDs provided!")
            return
        
        logging.info("=" * 60)
        logging.info("[TEST] TESTING LOCK WITH FEATURE TOGGLE")
        logging.info("=" * 60)
        
        logging.info("\n[TEST] Current feature states BEFORE lock:")
        self.log_feature_status()
        
        logging.info("\n[TEST] Simulating LOCK action...")
        # Don't actually lock, just toggle features
        self.disable_all_features(save=False)
        
        logging.info("\n[TEST] Feature states AFTER lock:")
        self.log_feature_status()
        
        logging.info("\n[TEST] Simulating UNLOCK action...")
        self.enable_all_features(save=False)
        
        logging.info("\n[TEST] Feature states AFTER unlock:")
        self.log_feature_status()
        
        logging.info("=" * 60)
        logging.info("[TEST] LOCK/UNLOCK FEATURE TOGGLE TEST COMPLETE")
        logging.info("[TEST] Note: Channel was NOT actually locked/unlocked")
        logging.info("[TEST] Note: Config file was NOT modified")
        logging.info("=" * 60)

    # ===========================
    # MAIN SCHEDULER FUNCTIONS
    # ===========================
    
    def check_all_tasks(self):
        """Check and execute all configured tasks"""
        # Check regular tasks
        for task_name, task_config in self.config.get('tasks', {}).items():
            try:
                self.execute_task(task_name, task_config)
            except Exception as e:
                logging.error(f"[ERROR] Error in task '{task_name}': {str(e)}", exc_info=True)
        
        # Check auto-cash (only runs if enabled)
        try:
            self.check_auto_cash()
        except Exception as e:
            logging.error(f"[ERROR] Error in auto-cash: {str(e)}", exc_info=True)
        
        # Check cash limits (only runs if enabled)
        try:
            self.check_cash_checks_schedule()
        except Exception as e:
            logging.error(f"[ERROR] Error in cash check: {str(e)}", exc_info=True)
        
        # Check role cash distribution (only runs if enabled)
        try:
            self.check_role_cash_schedule()
        except Exception as e:
            logging.error(f"[ERROR] Error in role cash: {str(e)}", exc_info=True)
    
    def run(self):
        """Main scheduler loop"""
        logging.info("=" * 60)
        logging.info("[START] Discord Channel Permission Scheduler STARTED")
        logging.info(f"[TIME] Timezone: {self.ist_tz}")
        logging.info(f"[INFO] Loaded {len(self.config.get('tasks', {}))} task(s)")
        logging.info("=" * 60)
        
        # Log feature toggle behavior
        logging.info("[INFO] 🔒 LOCK action will DISABLE all features")
        logging.info("[INFO] 🔓 UNLOCK action will ENABLE all features")
        logging.info("=" * 60)
        
        # Log current feature states
        self.log_feature_status()
        
        # Log auto-cash status
        auto_cash = self.config.get('auto_cash', {})
        if auto_cash.get('enabled', False):
            logging.info(f"[AUTO-CASH] ✅ ENABLED")
            logging.info(f"  Time: {auto_cash.get('time')}")
            logging.info(f"  Channel: {auto_cash.get('channel_id')}")
            logging.info(f"  Weekday amounts:")
            for day, amount in auto_cash.get('amounts', {}).items():
                amount_int = self.parse_amount(amount)
                logging.info(f"    {day}: {self.format_amount(amount_int)}")
        else:
            logging.info("[AUTO-CASH] ❌ DISABLED")
        
        # Log cash check status
        cash_checks = self.config.get('cash_checks', {})
        if cash_checks.get('enabled', False):
            logging.info(f"[CASH-CHECK] ✅ ENABLED")
            logging.info(f"  Interval: {cash_checks.get('check_interval_minutes')} minutes")
            logging.info(f"  Channel: {cash_checks.get('channel_id')}")
        else:
            logging.info("[CASH-CHECK] ❌ DISABLED")
        
        # Log role cash status
        role_cash = self.config.get('add_cash_to_roles', {})
        if role_cash.get('enabled', False):
            roles = role_cash.get('roles', {})
            logging.info(f"[ROLE-CASH] ✅ ENABLED")
            logging.info(f"  Interval: {role_cash.get('check_interval_minutes')} minutes")
            logging.info(f"  Channel: {role_cash.get('channel_id')}")
            logging.info(f"  Roles ({len(roles)}):")
            
            total_per_interval = 0
            for role_name, role_data in roles.items():
                if isinstance(role_data, dict):
                    for role_id, amount in role_data.items():
                        amount_int = self.parse_amount(amount)
                        total_per_interval += amount_int
                        logging.info(f"    {role_name}: {self.format_amount(amount_int)}")
            
            logging.info(f"  Total per interval: {self.format_amount(total_per_interval)}")
        else:
            logging.info("[ROLE-CASH] ❌ DISABLED")
        
        logging.info("=" * 60)
        
        # Log tasks
        logging.info("[TASKS] Scheduled tasks:")
        for task_name, task_config in self.config.get('tasks', {}).items():
            action = task_config.get('action', 'custom')
            action_icon = "🔒" if action == 'lock' else ("🔓" if action == 'unlock' else "⚙️")
            logging.info(f"  {action_icon} {task_name}: {task_config.get('lock_time')} IST ({action})")
        
        logging.info("=" * 60)
        
        # Schedule config reloading every 1 minute
        schedule.every(1).minutes.do(self.reload_config)
        
        # Track last check minute
        last_check_minute = None
        
        while True:
            try:
                current_time = datetime.now(self.ist_tz)
                current_minute = current_time.strftime('%Y-%m-%d_%H:%M')
                
                # Check tasks once per minute
                if current_minute != last_check_minute:
                    self.check_all_tasks()
                    last_check_minute = current_minute
                
                # Run other scheduled jobs (like config reload)
                schedule.run_pending()
                
                # Sleep for a shorter interval for better precision
                time.sleep(5)
                
            except KeyboardInterrupt:
                logging.info("\n[STOP] Scheduler stopped by user")
                break
            except Exception as e:
                logging.error(f"[ERROR] Critical error: {str(e)}", exc_info=True)
                time.sleep(60)


# ===========================
# ENTRY POINT
# ===========================

if __name__ == "__main__":
    scheduler = DiscordPermissionScheduler('config.json')
    
    # Uncomment one of these for testing:
    
    # === FEATURE TOGGLE TESTS ===
    # scheduler.test_feature_toggle()                   # Test enable/disable without saving
    # scheduler.test_lock_with_feature_toggle()         # Simulate lock/unlock with toggle
    # scheduler.log_feature_status()                    # Show current feature states
    
    # === GENERAL TESTS ===
    # scheduler.test_typing()                           # Test typing indicator
    
    # === AUTO-CASH TESTS ===
    # scheduler.test_auto_cash_single_day('Monday')     # Test auto-cash for a day
    # scheduler.test_auto_cash_all_days()               # Test auto-cash for all days
    # scheduler.simulate_weekday_execution('Monday')    # Simulate auto-cash execution
    
    # === CASH CHECK TESTS ===
    # scheduler.test_cash_check()                       # Test cash check immediately
    # scheduler.test_cumulative_calculation()           # Test limit calculation
    
    # === ROLE CASH TESTS ===
    # scheduler.list_configured_roles()                 # List all configured roles
    # scheduler.test_role_cash_dry_run()                # Dry run (no commands sent)
    # scheduler.test_role_cash_single('VIP')            # Test single role
    # scheduler.test_role_cash_all()                    # Test all roles
    
    # Normal operation
    scheduler.run()