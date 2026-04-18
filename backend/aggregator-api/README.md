# Aggregator API

## Setup

### 1. Create a virtual environment.

This keeps your project dependencies separate from other Python projects.

```bash
python3 -m venv venv
```

### 2. Activate the virtual environment.

- On macOS or Linux:
  ```bash
  source venv/bin/activate
  ```
- On Windows:
  ```bash
  venv\Scripts\activate
  ```

### 3. Install the required packages.

```bash
pip install fastapi uvicorn python-dotenv
```

### 4. Create a file named `.env` in your project folder.

Add your API key like this:

```env
API_KEY=your-secret-key-here
```

## Run the app

Start the server with:

```bash
uvicorn app.main:app --reload
```

## What this does

- `fastapi` runs the web API.
- `uvicorn` starts the server.
- `python-dotenv` loads values from your `.env` file.
- `--reload` automatically restarts the app when you make changes, which is useful during development.
