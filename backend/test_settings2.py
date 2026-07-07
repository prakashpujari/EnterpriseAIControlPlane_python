import os
os.chdir(r"C:\pp\GitHub\EnterpriseAIControlPlane_python\EnterpriseAIControlPlane_python\backend")
from app.config.settings import settings
print('PINECONE_API_KEY:', settings.PINECONE_API_KEY.get_secret_value())
print('GROQ_API_KEY:', settings.GROQ_API_KEY.get_secret_value())