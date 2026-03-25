import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

async def clean():
    conn = await asyncpg.connect(
        host=os.environ["POSTGRES_HOST"],
        port=int(os.environ["POSTGRES_PORT"]),
        database=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
    )
    await conn.execute("TRUNCATE campaign_results, campaigns, customers RESTART IDENTITY CASCADE")
    print("Listo. Tablas vacias: customers, campaigns, campaign_results")
    await conn.close()

asyncio.run(clean())
