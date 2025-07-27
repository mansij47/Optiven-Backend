# Optiven Backend

## Setup Instructions

Follow these steps to set up and run the project locally:

---

### 1️⃣ Create and activate virtual environment

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment (Linux/Mac)
source venv/bin/activate

# Activate virtual environment (Windows)
.\venv\Scripts\activate
```

---

### 2️⃣ Install dependencies

```bash
pip install -r requirements.txt
```

---

### 3️⃣ Run the application

```bash
uvicorn app.main:app --reload
```

---

✅ The app will be running at:  
**http://127.0.0.1:8000**

---

### Notes

- Make sure you have Python installed (preferably Python 3.10).
- If `uvicorn` is not installed, it will be installed automatically via `requirements.txt`.  
- The `--reload` flag is useful during development; it auto-reloads on code changes.
