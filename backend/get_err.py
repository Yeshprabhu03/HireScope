import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect("postgresql://postgres@localhost:5433/hirescope")
    row = await conn.fetchrow("SELECT error FROM jobs WHERE status='failed' ORDER BY created_at DESC LIMIT 1")
    print("DB ERROR:", row['error'])

asyncio.run(main())
