import asyncio
import asyncpg
import json

async def main():
    conn = await asyncpg.connect("postgresql://postgres@localhost:5433/hirescope")
    row = await conn.fetchrow("SELECT raw_html, parsed_data FROM jobs WHERE job_id='7553a098-a3e3-4c7c-baa4-34db47851565'")
    if row and row['parsed_data']:
        print("PARSED:", row['parsed_data'])
    elif row:
        print("Raw HTML fetched:", len(row['raw_html']) if row['raw_html'] else None)
    else:
        print("No row")
    await conn.close()
    
asyncio.run(main())
