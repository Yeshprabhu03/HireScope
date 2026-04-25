import asyncio
from utils.llm import _generate_gemini
from pydantic import BaseModel, Field

class TestSchema(BaseModel):
    name: str = Field(description="Name")

async def test():
    try:
        res = await _generate_gemini("What is the name of Apple's CEO?", 50, 0.0, response_schema=TestSchema)
        print("SUCCESS class:", res)
    except Exception as e:
        print("CLASS ERROR:", e)
        try:
            res = await _generate_gemini("What is the name of Apple's CEO?", 50, 0.0, response_schema=TestSchema.model_json_schema())
            print("SUCCESS dict:", res)
        except Exception as e:
            print("DICT ERROR:", e)

asyncio.run(test())
