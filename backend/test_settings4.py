# Test settings loading without triggering full app import
import sys
import os

# Change to backend directory
os.chdir(r"C:\pp\GitHub\EnterpriseAIControlPlane_python\EnterpriseAIControlPlane_python\backend")

# Import settings module directly
import importlib.util
spec = importlib.util.spec_from_file_location("settings", "app/config/settings.py")
settings_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(settings_module)

s = settings_module.Settings()
print('PINECONE_API_KEY:', s.PINECONE_API_KEY.get_secret_value())
print('GROQ_API_KEY:', s.GROQ_API_KEY.get_secret_value())
print('DATABASE_URL:', s.DATABASE_URL)