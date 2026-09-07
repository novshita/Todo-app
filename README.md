# To-Do App

A simple Flask To-Do list app with SQLite persistence, task priorities, due dates, and subtasks.

## Features

- Add, edit, complete, and delete tasks
- Set task priority and due date
- Add, complete, and delete subtasks per task
- Data persisted in SQLite (`tasks.db`)

## Run locally (without Docker)

```bash
pip install -r requirements.txt
python3 app.py
```

The app runs at `http://localhost:5000`.

## Run with Docker Compose

```bash
docker compose up --build
```

The app runs at `http://localhost:5000`. Task data is persisted in a named Docker volume (`todo-data`) mounted at `/data`, so it survives container restarts.

## Project structure

```
app.py               # Flask app: routes, DB setup, task/subtask logic
templates/index.html # UI (single page)
Dockerfile            # App container image
docker-compose.yml    # Compose service + persistent volume
requirements.txt      # Python dependencies
```

## Tech stack

- Python / Flask
- SQLite
- Docker / Docker Compose
