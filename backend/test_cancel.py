import asyncio
import redis.asyncio as aioredis
from app.redis.pubsub import subscribe_pattern
async def test():
    task = asyncio.create_task(run_sub())
    await asyncio.sleep(0.5)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    print('Cancelled.')
async def run_sub():
    async for _ in subscribe_pattern('conversation:*'):
        pass
asyncio.run(test())
