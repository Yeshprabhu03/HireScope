import asyncio
import traceback
from utils.llm import llm_generate_json
from pydantic import BaseModel, Field

class TestSchema(BaseModel):
    name: str = Field(default="Unknown", description="Name")

async def test():
    try:
        res = await llm_generate_json("What is the name of Apple CEO?", response_schema=TestSchema)
        open('/tmp/test_out.txt', 'w').write(str(res))
    except Exception as e:
        open('/tmp/test_out.txt', 'w').write(str(e) + '\n' + traceback.format_exc())

asyncio.run(test())
