import asyncio
import redis.asyncio as aioredis
from app.core.config import settings
import json
async def test():
    r = aioredis.from_url(settings.REDIS_URL, encoding='utf-8', decode_responses=True)
    pubsub = r.pubsub()
    await pubsub.psubscribe('conversation:*')
    print('Subscribed')
    async for raw in pubsub.listen():
        print(raw)
        break
    await pubsub.punsubscribe('conversation:*')
    await pubsub.aclose()
async def pub():
    r = aioredis.from_url(settings.REDIS_URL, encoding='utf-8', decode_responses=True)
    await asyncio.sleep(1)
    await r.publish('conversation:123', json.dumps({'msg':'hello'}))
async def main():
    await asyncio.gather(test(), pub())
asyncio.run(main())
