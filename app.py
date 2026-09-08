import sqlite3
import os
import json
import calendar
from datetime import date, timedelta
from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)

DATABASE = os.environ.get("DATABASE_PATH", "tasks.db")


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    os.makedirs(os.path.dirname(DATABASE) or ".", exist_ok=True)
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                text     TEXT    NOT NULL,
                done     INTEGER NOT NULL DEFAULT 0,
                priority TEXT    NOT NULL DEFAULT 'medium',
                due_date TEXT             DEFAULT '',
                subtasks TEXT             DEFAULT '[]'
            )
        """)
        # migrate: add subtasks column if upgrading from an older DB
        cols = [r[1] for r in conn.execute("PRAGMA table_info(tasks)").fetchall()]
        if "subtasks" not in cols:
            conn.execute("ALTER TABLE tasks ADD COLUMN subtasks TEXT DEFAULT '[]'")


init_db()


def parse_subtasks(subtasks_json):
    try:
        return json.loads(subtasks_json or "[]")
    except:
        return []


def serialize_subtasks(subtasks):
    return json.dumps(subtasks)


@app.route("/")
def index():
    edit_id = request.args.get("edit", type=int, default=-1)
    query = request.args.get("q", "").strip()
    date_filter = request.args.get("date", "").strip()

    today = date.today()
    selected_date = date.fromisoformat(date_filter) if date_filter else today
    week_start = selected_date - timedelta(days=(selected_date.isoweekday() % 7))
    week_days = [week_start + timedelta(days=i) for i in range(7)]

    with get_db() as conn:
        if query:
            task_rows = conn.execute(
                "SELECT * FROM tasks WHERE text LIKE ? ORDER BY id",
                (f"%{query}%",)
            ).fetchall()
        elif date_filter:
            task_rows = conn.execute(
                "SELECT * FROM tasks WHERE due_date = ? ORDER BY id",
                (date_filter,)
            ).fetchall()
        else:
            task_rows = conn.execute("SELECT * FROM tasks ORDER BY id").fetchall()
        tasks = []
        for row in task_rows:
            task_dict = dict(row)
            task_dict["subtasks"] = parse_subtasks(task_dict["subtasks"])
            tasks.append(task_dict)

    tasks_by_priority = {
        "high": [t for t in tasks if t["priority"] == "high"],
        "medium": [t for t in tasks if t["priority"] == "medium"],
        "low": [t for t in tasks if t["priority"] == "low"],
    }

    return render_template(
        "index.html", tasks=tasks, tasks_by_priority=tasks_by_priority,
        edit_id=edit_id, query=query, date_filter=date_filter,
        week_days=week_days, today=today, selected_date=selected_date,
    )


@app.route("/calendar")
def calendar_view():
    today = date.today()
    year = request.args.get("year", type=int, default=today.year)
    month = request.args.get("month", type=int, default=today.month)

    if month < 1:
        year, month = year - 1, 12
    elif month > 12:
        year, month = year + 1, 1

    with get_db() as conn:
        rows = conn.execute(
            "SELECT due_date, COUNT(*) AS count FROM tasks WHERE due_date != '' GROUP BY due_date"
        ).fetchall()
    task_counts = {row["due_date"]: row["count"] for row in rows}

    cal = calendar.Calendar(firstweekday=6)  # weeks start on Sunday
    weeks = []
    for week in cal.monthdatescalendar(year, month):
        weeks.append([
            {
                "day": day.day,
                "date": day.isoformat(),
                "in_month": day.month == month,
                "is_today": day == today,
                "count": task_counts.get(day.isoformat(), 0),
            }
            for day in week
        ])

    prev_year, prev_month = (year - 1, 12) if month == 1 else (year, month - 1)
    next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)

    return render_template(
        "calendar.html",
        weeks=weeks,
        month_name=calendar.month_name[month],
        year=year,
        prev_year=prev_year, prev_month=prev_month,
        next_year=next_year, next_month=next_month,
    )


@app.route("/add", methods=["POST"])
def add():
    task = request.form.get("task")
    priority = request.form.get("priority", "medium")
    due_date = request.form.get("due_date", "")
    if task:
        with get_db() as conn:
            conn.execute(
                "INSERT INTO tasks (text, priority, due_date, subtasks) VALUES (?, ?, ?, ?)",
                (task, priority, due_date, "[]")
            )
    return redirect(url_for("index"))


@app.route("/edit/<int:task_id>", methods=["POST"])
def edit(task_id):
    new_text = request.form.get("text")
    if new_text:
        with get_db() as conn:
            conn.execute("UPDATE tasks SET text = ? WHERE id = ?",
                         (new_text, task_id))
    return redirect(url_for("index"))


@app.route("/toggle/<int:task_id>")
def toggle(task_id):
    with get_db() as conn:
        conn.execute(
            "UPDATE tasks SET done = NOT done WHERE id = ?", (task_id,))
    return redirect(url_for("index"))


@app.route("/delete/<int:task_id>")
def delete(task_id):
    with get_db() as conn:
        conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    return redirect(url_for("index"))


@app.route("/add-subtask/<int:task_id>", methods=["POST"])
def add_subtask(task_id):
    subtask_text = request.form.get("subtask_text")
    if subtask_text:
        with get_db() as conn:
            task_row = conn.execute(
                "SELECT subtasks FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if task_row:
                subtasks = parse_subtasks(task_row["subtasks"])
                new_id = max([s["id"] for s in subtasks], default=0) + 1
                subtasks.append(
                    {"id": new_id, "text": subtask_text, "done": False})
                conn.execute("UPDATE tasks SET subtasks = ? WHERE id = ?",
                             (serialize_subtasks(subtasks), task_id))
    return redirect(url_for("index"))


@app.route("/toggle-subtask/<int:task_id>/<int:subtask_id>")
def toggle_subtask(task_id, subtask_id):
    with get_db() as conn:
        task_row = conn.execute(
            "SELECT subtasks FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if task_row:
            subtasks = parse_subtasks(task_row["subtasks"])
            for subtask in subtasks:
                if subtask["id"] == subtask_id:
                    subtask["done"] = not subtask["done"]
                    break
            conn.execute("UPDATE tasks SET subtasks = ? WHERE id = ?",
                         (serialize_subtasks(subtasks), task_id))
    return redirect(url_for("index"))


@app.route("/delete-subtask/<int:task_id>/<int:subtask_id>")
def delete_subtask(task_id, subtask_id):
    with get_db() as conn:
        task_row = conn.execute(
            "SELECT subtasks FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if task_row:
            subtasks = parse_subtasks(task_row["subtasks"])
            subtasks = [s for s in subtasks if s["id"] != subtask_id]
            conn.execute("UPDATE tasks SET subtasks = ? WHERE id = ?",
                         (serialize_subtasks(subtasks), task_id))
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
