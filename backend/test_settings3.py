# Test settings loading without triggering full app import
import sys
import os

# Change to backend directory
os.chdir(r"C:\pp\GitHub\EnterpriseAIControlPlane_python\EnterpriseAIControlPlane_python\backend")

# Import settings directly without going through app.__init__
from app.config.settings import Settings

# Create a fresh instance to see what it loads
s = Settings()
print('PINECONE_API_KEY:', s.PINECONE_API_KEY.get_secret_value())
print('GROQ_API_KEY:', s.GROQ_API_KEY.get_secret_value())
print('DATABASE_URL:', s.DATABASE_URL)