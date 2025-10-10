import ssl, certifi, asyncio, asyncpg

async def main():
    ssl_ctx = ssl.create_default_context(cafile=certifi.where())
    conn = await asyncpg.connect(
        user="postgres.xgbnyqfzlyviwequqxga",
        password="QWWNoJD9oIcHCMK6",
        host="aws-1-us-east-2.pooler.supabase.com",
        port=6543,
        database="postgres",
        ssl=ssl_ctx,
    )
    print("OK SSL")
    await conn.close()

asyncio.run(main())