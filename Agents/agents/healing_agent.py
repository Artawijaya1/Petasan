import os
import json


def _get_client():
    from openai import OpenAI

    api_key = os.environ.get("BOB_API_KEY")
    if not api_key:
        raise RuntimeError("BOB_API_KEY belum diatur. Isi Agents/.env sebelum menjalankan agent.")
    return OpenAI(
        api_key=api_key,
        base_url=os.environ.get("BOB_BASE_URL", "https://bob.ibm.com/api"),
    )

def diagnose_and_fix(command_failed: str, stderr_log: str, attempt: int) -> dict:
    system_prompt = """
    Kamu adalah Auto-Healing DevOps Agent.
    Tugasmu adalah menganalisis error log terminal dan memberikan perbaikan spesifik.
    
    Tugasmu:
    1. Berikan alasan kenapa error terjadi (Thought Process).
    2. Berikan 1 perintah perbaikan terminal yang tepat untuk dicoba ulang.

    Format JSON Response:
    {
      "thought_title": "Judul Singkat Masalah",
      "thought_detail": "Penjelasan mendalam penyebab error...",
      "fix_command": "perintah perbaikan terminal baru"
    }
    """

    user_prompt = f"""
    Perintah yang gagal: {command_failed}
    Error Log (stderr):
    {stderr_log[-1500:]}

    Percobaan ke-{attempt}. Berikan diagnosis dan perintah perbaikan baru.
    """

    response = _get_client().chat.completions.create(
        model=os.environ.get("BOB_MODEL", "bob"),
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        response_format={"type": "json_object"}
    )

    return json.loads(response.choices[0].message.content)
