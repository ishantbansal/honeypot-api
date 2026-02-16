"""Human-like behavior simulation to evade bot detection."""

import random
import asyncio
from app.config import settings

# Enable/disable human-like delays (disabled for testing, enabled for production)
ENABLE_HUMAN_DELAY = settings.enable_human_delay


async def simulate_human_delay(message_length: int, complexity: str = "normal") -> float:
    """
    Simulate realistic human response time.

    Args:
        message_length: Length of response to type
        complexity: "simple", "normal", "complex"

    Returns:
        Total delay in seconds
    """
    # Skip delay if disabled (for testing)
    if not ENABLE_HUMAN_DELAY:
        await asyncio.sleep(0.1)  # Minimal delay for realism
        return 0.1

    # 1. Reading time (scammer's message)
    read_time = random.uniform(3, 10)

    # 2. Comprehension time
    comprehension_time = random.uniform(2, 8)

    # 3. Thinking time
    thinking_times = {
        "simple": (2, 8),
        "normal": (5, 15),
        "complex": (10, 25)
    }
    thinking_range = thinking_times.get(complexity, thinking_times["normal"])
    thinking_time = random.uniform(*thinking_range)

    # 4. Typing time (elderly: 30-60 chars/min = 0.5-1.0 chars/sec)
    chars_per_second = random.uniform(0.5, 1.0)
    typing_time = message_length / chars_per_second

    # 5. Random pauses (distraction)
    pause_time = 0
    if random.random() < 0.3:  # 30% chance
        pause_time = random.uniform(5, 20)

    # Total delay
    total_delay = read_time + comprehension_time + thinking_time + typing_time + pause_time

    # Clamp to realistic range (10-90 seconds)
    total_delay = min(max(total_delay, 10), 90)

    await asyncio.sleep(total_delay)
    return total_delay


async def simulate_distraction_delay() -> float:
    """
    Simulate user getting distracted (10% chance).

    Returns:
        Delay in seconds (0 if no distraction)
    """
    # Skip if delays disabled
    if not ENABLE_HUMAN_DELAY:
        return 0.0

    if random.random() < 0.1:  # 10% chance
        delay = random.uniform(60, 180)  # 1-3 minutes
        await asyncio.sleep(delay)
        return delay
    return 0.0
