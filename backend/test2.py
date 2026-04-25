import asyncio
from utils.llm import llm_generate_json
from pydantic import BaseModel, Field

class TestSchema(BaseModel):
    name: str = Field(default="Unknown", description="Name")

async def test():
    try:
        res = await llm_generate_json("What is the name of Apple's CEO?", response_schema=TestSchema)
        print("SUCCESS:", res)
    except Exception as e:
        print("ERROR_TYPE:", type(e))
        print("ERROR_VAL:", str(e))
        import traceback
        traceback.print_exc()

asyncio.run(test())
