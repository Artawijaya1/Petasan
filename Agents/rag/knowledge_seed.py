# rag/knowledge_seed.py
"""
Data awal (seed) knowledge base untuk RAG healing agent.
Setiap entry merepresentasikan satu jenis error yang pernah dikenali,
beserta penjelasan dan solusi yang terbukti bekerja.

Tambahkan entry baru di sini seiring bertambahnya pengalaman debugging tim.
"""

KNOWLEDGE_SEED: list[dict] = [
    {
        "id": "eaddrinuse",
        "text": "Error EADDRINUSE: port sudah digunakan oleh proses lain yang masih berjalan di background.",
        "known_fix": "npx kill-port {port}",
        "category": "port_conflict",
    },
    {
        "id": "module_not_found",
        "text": "Error Cannot find module atau Module not found: dependency belum terinstall atau folder node_modules rusak/corrupt.",
        "known_fix": "rm -rf node_modules package-lock.json && npm install",
        "category": "missing_dependency",
    },
    {
        "id": "permission_denied",
        "text": "Error permission denied atau EACCES saat menjalankan binary di node_modules/.bin, biasanya karena file executable kehilangan permission execute.",
        "known_fix": "chmod +x ./node_modules/.bin/*",
        "category": "permission",
    },
    {
        "id": "python_module_not_found",
        "text": "Error ModuleNotFoundError di Python: package belum terinstall di environment yang sedang aktif, atau virtual environment belum diaktifkan.",
        "known_fix": "pip install -r requirements.txt",
        "category": "missing_dependency",
    },
    {
        "id": "engine_version_mismatch",
        "text": "Error terkait unsupported engine atau versi Node tidak sesuai dengan yang diminta di package.json (field engines).",
        "known_fix": "nvm install --lts && nvm use --lts",
        "category": "version_mismatch",
    },
    {
        "id": "enoent_file_missing",
        "text": "Error ENOENT: file atau direktori yang dibutuhkan tidak ditemukan, sering terjadi kalau folder belum ter-generate dari proses build sebelumnya.",
        "known_fix": "npm install && npm run build",
        "category": "missing_file",
    },
    
]