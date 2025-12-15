from fastapi import FastAPI, Depends, HTTPException
import asyncpg
import redis.asyncio as redis
import os

app = FastAPI(title="FastAPI DevContainer Example")

# 依赖项：获取数据库连接
async def get_db():
    conn = await asyncpg.connect(os.getenv('DATABASE_URL'))
    try:
        yield conn
    finally:
        await conn.close()

# 依赖项：获取Redis客户端
async def get_redis():
    redis_client = redis.from_url(os.getenv('REDIS_URL'))
    try:
        yield redis_client
    finally:
        await redis_client.close()

@app.get("/")
async def read_root():
    return {"message": "Hello from FastAPI in DevContainer!"}

@app.get("/users/{user_id}")
async def read_user(user_id: int, 
                   db=Depends(get_db), 
                   redis_client=Depends(get_redis)):
    # 首先尝试从Redis缓存获取
    cache_key = f"user:{user_id}"
    cached = await redis_client.get(cache_key)
    if cached:
        return {"user": cached, "source": "cache"}
    
    # 缓存未命中，查询数据库
    user = await db.fetchrow("SELECT * FROM users WHERE id = $1", user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # 将结果存入缓存
    await redis_client.setex(cache_key, 3600, user['name'])  # 缓存1小时
    return {"user": user['name'], "source": "database"}

@app.post("/users/{user_name}")
async def create_user(user_name: str, db=Depends(get_db)):
    user_id = await db.fetchval(
        "INSERT INTO users(name) VALUES($1) RETURNING id", 
        user_name
    )
    return {"user_id": user_id, "name": user_name}
