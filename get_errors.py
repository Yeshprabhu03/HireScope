import asyncio
import asyncpg
import traceback

async def main():
    try:
        conn = await asyncpg.connect("postgresql://postgres@localhost:5433/hirescope")
        rows = await conn.fetch("SELECT job_url, status, error, created_at FROM jobs ORDER BY created_at DESC LIMIT 5")
        for r in rows:
            print(r['job_url'], r['status'], r['error'])
    except Exception:
        traceback.print_exc()

asyncio.run(main())
