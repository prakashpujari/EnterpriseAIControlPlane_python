from pydantic_settings import BaseSettings
from pydantic import SecretStr

class TestSettings(BaseSettings):
    PINECONE_API_KEY: SecretStr
    class Config:
        env_file = '.env'
        env_file_encoding = 'utf-8'

s = TestSettings()
print('Key:', s.PINECONE_API_KEY.get_secret_value())