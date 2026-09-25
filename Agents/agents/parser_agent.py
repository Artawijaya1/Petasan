import os
import json
from openai import OpenAI

# Bob inference API — OpenAI-compatible endpoint
# Gunakan Inference API key dari bob.ibm.com (scope: Inference)
# Set env var: BOB_API_KEY dan BOB_BASE_URL
client = OpenAI(
    api_key=os.environ.get("BOB_API_KEY"),
    base_url=os.environ.get("BOB_BASE_URL", "https://bob.ibm.com/api"),
)

def scan_repository(repo_path: str) -> dict:
    files_to_check = ['package.json', 'requirements.txt', 'Dockerfile', 'docker-compose.yml', '.env.example', 'README.md']
    found_files = {}

    for file_name in files_to_check:
        full_path = os.path.join(repo_path, file_name)
        if os.path.exists(full_path):
            with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                # Ambil 2000 karakter pertama agar token efisien
                found_files[file_name] = f.read(2000)

    prompt = f"""
    Kamu adalah DevOps Architect Agent.
    Berdasarkan isi file repository berikut, buat rencana instalasi berupa JSON array of commands.
    
    File yang ditemukan:
    {json.dumps(found_files, indent=2)}

    Format Output Harus Berupa JSON Valid:
    {{
      "env_needed": true,
      "commands": [
        "npm install",
        "npm run dev"
      ]
    }}
    """

    response = client.chat.completions.create(
        model=os.environ.get("BOB_MODEL", "bob"),
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )

    return json.loads(response.choices[0].message.content)
