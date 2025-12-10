"""
TF System API Client for Discord Bot
This module provides an easy-to-use Python client for interacting with TF_System API from your Discord bot."""

import aiohttp
import os
from typing import Optional, Dict, List, Tuple
from datetime import datetime


# Rank hierarchy (lower number = lower rank)
RANK_HIERARCHY = {
    'Aspirant': 1,
    'Novice': 2,
    'Adept': 3,
    'Crusader': 4,
    'Paladin': 5,
    'Exemplar': 6,
    'Prospect': 7,
    'Commander': 8,
    'Marshal': 9,
    'General': 10,
    'Chief General': 11
}


def get_rank_level(rank_name: str) -> int:
    """
    Get the hierarchy level of a rank.
    
    Args:
        rank_name: Name of the rank
    
    Returns:
        int: Hierarchy level (1-11), or 0 if rank is unknown
    """
    return RANK_HIERARCHY.get(rank_name, 0)


def can_modify_rank(user_rank: str, target_rank: str, target_member_id: int = None, user_member_id: int = None) -> Tuple[bool, str]:
    """
    Check if a user has permission to modify a target member's rank.
    
    Rules:
    - Users can only change ranks of members below their own rank
    - Users cannot change their own rank
    - Users cannot change ranks of members at the same level or higher
    
    Args:
        user_rank: The rank of the user attempting the change
        target_rank: The current rank of the target member
        target_member_id: Optional member ID of target (for self-check)
        user_member_id: Optional member ID of user (for self-check)
    
    Returns:
        tuple: (can_modify: bool, reason: str)
    """
    # Check if trying to modify own rank
    if target_member_id and user_member_id and target_member_id == user_member_id:
        return False, "You cannot change your own rank."
    
    user_level = get_rank_level(user_rank)
    target_level = get_rank_level(target_rank)
    
    # Unknown rank check
    if user_level == 0:
        return False, f"Unknown user rank: {user_rank}"
    if target_level == 0:
        return False, f"Unknown target rank: {target_rank}"
    
    # Permission check: user must be higher rank than target
    if user_level <= target_level:
        return False, (
            f"You don't have permission to change this member's rank. "
            f"The target is a **{target_rank}** and you are a **{user_rank}**. "
            f"You can only change ranks of members below your level."
        )
    
    return True, "Permission granted"


class TFSystemAPI:
    """
    Client for interacting with TF System API
    
    Usage:
        api = TFSystemAPI(
            api_url="https://your-tf-system.onrender.com/api/v1",
            api_key="your-api-key-here"
        )
        
        # Get all members
        members = await api.get_members()
        
        # Change rank
        result = await api.change_member_rank(
            member_id=1,
            new_rank="Commander",
            discord_user_id=str(ctx.author.id)
        )
    """
    
    def __init__(self, api_url: str = None, api_key: str = None):
        """
        Initialize the API client
        
        Args:
            api_url: Base URL of the TF System API (e.g., https://your-app.onrender.com/api/v1)
            api_key: API key for authentication
        """
        self.api_url = api_url or os.getenv('TF_SYSTEM_API_URL', 'http://localhost:5000/api/v1')
        self.api_key = api_key or os.getenv('TF_SYSTEM_API_KEY', '')
        
        if not self.api_key:
            raise ValueError("API key must be provided or set in TF_SYSTEM_API_KEY environment variable")
        
        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
    
    async def _request(self, method: str, endpoint: str, **kwargs) -> Dict:
        """Make an HTTP request to the API"""
        url = f"{self.api_url}{endpoint}"
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.request(method, url, headers=self.headers, **kwargs) as response:
                    data = await response.json()
                    
                    # Check for rate limiting
                    if response.status == 429:
                        return {
                            'success': False,
                            'error': 'rate_limit',
                            'message': 'Rate limit exceeded. Please wait a moment and try again.',
                            **data
                        }
                    
                    return data
            except aiohttp.ClientError as e:
                return {
                    'success': False,
                    'error': 'connection_error',
                    'message': f'Failed to connect to TF System: {str(e)}'
                }
            except Exception as e:
                return {
                    'success': False,
                    'error': 'unknown_error',
                    'message': f'Unexpected error: {str(e)}'
                }
    
    # ========================================
    # SYSTEM STATUS
    # ========================================
    
    async def get_status(self) -> Dict:
        """
        Get system status
        
        Returns:
            dict: System status information
        """
        return await self._request('GET', '/status')
    
    async def verify_auth(self) -> Dict:
        """
        Verify API authentication
        
        Returns:
            dict: Authentication verification result
        """
        return await self._request('POST', '/auth/verify')
    
    # ========================================
    # MEMBER MANAGEMENT
    # ========================================
    
    async def get_members(self, search: str = None, rank: str = None, limit: int = 100) -> Dict:
        """
        Get list of all active members
        
        Args:
            search: Search query (username or rank)
            rank: Filter by specific rank
            limit: Maximum number of results
        
        Returns:
            dict: List of members
        """
        params = {}
        if search:
            params['search'] = search
        if rank:
            params['rank'] = rank
        if limit:
            params['limit'] = limit
        
        return await self._request('GET', '/members', params=params)
    
    async def get_member(self, member_id: int) -> Dict:
        """
        Get detailed information about a specific member
        
        Args:
            member_id: Member ID
        
        Returns:
            dict: Member details including activities and rank history
        """
        return await self._request('GET', f'/members/{member_id}')
    
    async def search_member(self, name: str, field: str = 'both') -> Dict:
        """
        Search for a member by name
        
        Args:
            name: Name to search for
            field: Field to search ('discord_username', 'roblox_username', or 'both')
        
        Returns:
            dict: Search results
        """
        params = {'q': name, 'field': field}
        return await self._request('GET', '/members/search', params=params)
    
    async def change_member_rank(self, member_id: int, new_rank: str, 
                                  reason: str = None, discord_user_id: str = None) -> Dict:
        """
        Change a member's rank
        
        Args:
            member_id: Member ID
            new_rank: New rank name
            reason: Reason for rank change
            discord_user_id: Discord user ID who made the change
        
        Returns:
            dict: Rank change result
        """
        data = {
            'rank': new_rank,
            'reason': reason or 'Changed via Discord Bot',
            'promoted_by': 'Discord Bot'
        }
        
        if discord_user_id:
            data['discord_user_id'] = discord_user_id
        
        return await self._request('PATCH', f'/members/{member_id}/rank', json=data)
    
    async def add_member(self, discord_username: str, roblox_username: str = None,
                        current_rank: str = 'Aspirant', discord_user_id: str = None) -> Dict:
        """
        Add a new member to the system
        
        Args:
            discord_username: Discord username (required)
            roblox_username: Roblox username (optional)
            current_rank: Initial rank (default: Aspirant)
            discord_user_id: Discord user ID who added the member
        
        Returns:
            dict: Add member result
        """
        data = {
            'discord_username': discord_username,
            'current_rank': current_rank
        }
        
        if roblox_username:
            data['roblox_username'] = roblox_username
        
        if discord_user_id:
            data['discord_user_id'] = discord_user_id
        
        return await self._request('POST', '/members', json=data)
    
    async def remove_member(self, member_id: int, discord_user_id: str = None) -> Dict:
        """
        Remove a member (mark as inactive)
        
        Args:
            member_id: Member ID
            discord_user_id: Discord user ID who removed the member
        
        Returns:
            dict: Remove member result
        """
        data = {}
        if discord_user_id:
            data['discord_user_id'] = discord_user_id
        
        return await self._request('DELETE', f'/members/{member_id}', json=data)
    
    # ========================================
    # RANK MANAGEMENT
    # ========================================
    
    async def get_ranks(self) -> Dict:
        """
        Get list of all available ranks
        
        Returns:
            dict: List of ranks with Roblox mappings
        """
        return await self._request('GET', '/ranks')
    
    # ========================================
    # ACTIVITY MANAGEMENT
    # ========================================
    
    async def log_activity(self, member_id: int, activity_type: str,
                          description: str = None, activity_date: str = None,
                          discord_user_id: str = "Cortex") -> Dict:
        """
        Log an activity for a member
        
        Args:
            member_id: Member ID
            activity_type: Type of activity (Raid, Patrol, Training, Mission, Tryout)
            description: Activity description
            activity_date: Date in YYYY-MM-DD format (default: today)
            discord_user_id: Discord user ID who logged the activity
        
        Returns:
            dict: Log activity result
        """
        data = {
            'member_id': member_id,
            'activity_type': activity_type
        }
        
        if description:
            data['description'] = description
        
        if activity_date:
            data['activity_date'] = activity_date
        
        if discord_user_id:
            data['discord_user_id'] = discord_user_id
        
        return await self._request('POST', '/activity', json=data)
    
    async def get_member_activities(self, member_id: int, limit: int = 20) -> Dict:
        """
        Get activities for a specific member
        
        Args:
            member_id: Member ID
            limit: Number of activities to return
        
        Returns:
            dict: List of activities
        """
        params = {'limit': limit}
        return await self._request('GET', f'/members/{member_id}/activities', params=params)
    
    # ========================================
    # HELPER METHODS
    # ========================================
    
    async def find_member_by_name(self, name: str) -> Optional[Dict]:
        """
        Find a member by Discord or Roblox username
        
        Args:
            name: Name to search for
        
        Returns:
            dict or None: Member info if found, None otherwise
        """
        result = await self.search_member(name)
        
        if result.get('success') and result.get('matches'):
            return result['matches'][0]
        
        return None
    
    async def change_rank_by_name(self, member_name: str, new_rank: str,
                                   reason: str = None, discord_user_id: str = None,
                                   user_rank: str = None) -> Dict:
        """
        Change a member's rank by name (convenience method)
        
        Args:
            member_name: Discord or Roblox username
            new_rank: New rank name
            reason: Reason for rank change
            discord_user_id: Discord user ID who made the change
            user_rank: Rank of the user making the change (for permission checking)
        
        Returns:
            dict: Rank change result
        """
        # Find member first
        member = await self.find_member_by_name(member_name)
        
        if not member:
            return {
                'success': False,
                'error': 'member_not_found',
                'message': f'Could not find member with name "{member_name}"'
            }
        
        # Check permissions if user_rank is provided
        if user_rank:
            can_modify, reason_msg = can_modify_rank(
                user_rank=user_rank,
                target_rank=member['current_rank']
            )
            
            if not can_modify:
                return {
                    'success': False,
                    'error': 'permission_denied',
                    'message': reason_msg
                }
        
        # Change rank
        return await self.change_member_rank(
            member_id=member['id'],
            new_rank=new_rank,
            reason=reason,
            discord_user_id=discord_user_id
        )


# Example usage in a Discord bot
if __name__ == '__main__':
    import asyncio
    
    async def example():
        # Initialize API client
        api = TFSystemAPI(
            api_url="http://localhost:5000/api/v1",
            api_key="your-api-key-here"
        )
        
        # Check system status
        status = await api.get_status()
        print(f"System Status: {status}")
        
        # Search for a member
        search_result = await api.search_member("João")
        print(f"Search Result: {search_result}")
        
        # Change rank by name
        rank_change = await api.change_rank_by_name(
            member_name="João",
            new_rank="Commander",
            reason="Promoted for outstanding performance"
        )
        print(f"Rank Change: {rank_change}")
    
    # Run example
    asyncio.run(example())



