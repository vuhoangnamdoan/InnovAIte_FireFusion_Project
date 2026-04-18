from pydantic_settings import BaseSettings

# gets from environment variables (case-insensitive)
class Environment(BaseSettings):
    broker_url: str

environment = Environment() # type: ignore