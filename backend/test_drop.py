import asyncio
# pyrefly: ignore [missing-import]
import redis.asyncio as aioredis
from app.redis.pubsub import subscribe_pattern
from app.core.config import settings
async def test():
    try:
        async for _ in subscribe_pattern('conversation:*'):
            print('waiting')
            # drop connection here by killing redis or closing it
    except Exception as e:
        print('Caught:', type(e), e)
asyncio.run(test())
