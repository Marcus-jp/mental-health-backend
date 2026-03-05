#!/usr/bin/env bash
set -o errexit

pip install --upgrade pip
pip install -r requirements.txt
```

### **File 6: `backend/.gitignore`**
```
__pycache__/
*.pyc
*.pyo
.Python
venv/
env/
.venv
.env
.DS_Store
*.pkl
*.joblib
models/