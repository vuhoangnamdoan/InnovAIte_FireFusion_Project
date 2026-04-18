from redis import asyncio
import os

cache_url = os.environ["CACHE_URL"]

cache_client = asyncio.Redis(host='cache', port=6379, db=0)
