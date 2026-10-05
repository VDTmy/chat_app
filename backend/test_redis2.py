import asyncio
import redis.asyncio as aioredis
async def test():
    r = aioredis.from_url('redis://localhost:6379/0')
    print('Redis aclose:', hasattr(r, 'aclose'))
    print('Redis close:', hasattr(r, 'close'))
asyncio.run(test())
