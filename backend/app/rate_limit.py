from app.redis import redis_client

async def check_rate_limit(api_key: str, quota_limit: int):
    redis_key = f"rate_limit:{api_key}"
    
    request_count=await redis_client.incr(redis_key)
    
    if request_count==1:
        await redis_client.expire(redis_key, 60)
        
    if request_count > quota_limit:
        return False
    return True
        