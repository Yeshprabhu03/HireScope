import os
import sys
import pytest
from dotenv import load_dotenv

# Add backend directory to path so tests can import from it easily
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend'))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

@pytest.fixture(scope="session", autouse=True)
def load_env():
    """Load environment variables once for the duration of the test session."""
    env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '.env'))
    if os.path.exists(env_path):
        load_dotenv(env_path)

    # Ensure a non-placeholder API key is available for live evaluation,
    # but don't fail immediately in case the tests use mocks or another provider.
    if os.environ.get("GEMINI_API_KEY") == "placeholder":
        print("WARNING: GEMINI_API_KEY is set to 'placeholder'. Live LLM evaluations may fail.")

@pytest.fixture
def anyio_backend():
    """Configure pytest-asyncio to use asyncio by default."""
    return "asyncio"
