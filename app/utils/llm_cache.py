"""Simple LLM response caching to reduce API calls."""

import hashlib
import json
from typing import Optional, Dict, Any
from datetime import datetime, timedelta


class LLMCache:
    """In-memory cache for LLM responses."""

    def __init__(self, ttl_minutes: int = 60):
        """Initialize cache.

        Args:
            ttl_minutes: Time to live for cache entries
        """
        self._cache: Dict[str, Dict[str, Any]] = {}
        self.ttl = timedelta(minutes=ttl_minutes)

    def _hash_key(self, prompt: str, model: str) -> str:
        """Generate cache key from prompt and model."""
        content = f"{model}:{prompt}"
        return hashlib.md5(content.encode()).hexdigest()

    def get(self, prompt: str, model: str) -> Optional[str]:
        """Get cached response if exists and not expired.

        Args:
            prompt: LLM prompt
            model: Model name

        Returns:
            Cached response or None
        """
        key = self._hash_key(prompt, model)
        if key in self._cache:
            entry = self._cache[key]
            # Check if expired
            if datetime.now() - entry["timestamp"] < self.ttl:
                return entry["response"]
            else:
                # Expired, remove
                del self._cache[key]
        return None

    def set(self, prompt: str, model: str, response: str):
        """Cache LLM response.

        Args:
            prompt: LLM prompt
            model: Model name
            response: LLM response to cache
        """
        key = self._hash_key(prompt, model)
        self._cache[key] = {
            "response": response,
            "timestamp": datetime.now()
        }

    def clear_expired(self):
        """Clear expired cache entries."""
        now = datetime.now()
        expired_keys = [
            key for key, entry in self._cache.items()
            if now - entry["timestamp"] >= self.ttl
        ]
        for key in expired_keys:
            del self._cache[key]

    def get_stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        return {
            "total_entries": len(self._cache),
            "memory_kb": len(str(self._cache)) // 1024
        }


# Global cache instance
llm_cache = LLMCache(ttl_minutes=60)
