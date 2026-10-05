import asyncio
# pyrefly: ignore [missing-import]
import redis.asyncio as aioredis
async def test():
    r = aioredis.from_url('redis://localhost:6379/0')
    p = r.pubsub()
    print('aclose:', hasattr(p, 'aclose'))
    print('close:', hasattr(p, 'close'))
asyncio.run(test())
