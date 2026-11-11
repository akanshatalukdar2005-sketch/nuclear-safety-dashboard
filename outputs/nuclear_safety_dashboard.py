"""Nuclear plant safety dashboard using SQLite and Tkinter/ipywidgets.

Run as a normal Python script for a Tkinter window. In Jupyter/Colab, run
%run nuclear_safety_dashboard.py (or execute the file) for an ipywidgets UI.
Set NUCLEAR_DB_PATH to choose a database file; otherwise nuclear_safety.db is
created beside this script. Notebook use requires ipywidgets.

The Tkinter CRUD pattern is informed by w3resource's SQLite CRUD exercise:
https://www.w3resource.com/python-exercises/tkinter/python-tkinter-file-operations-and-integration-exercise-12.php
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import Any


APP_TITLE = "Nuclear Plant Safety Dashboard"
DB_PATH = Path(os.environ.get("NUCLEAR_DB_PATH", Path(__file__).with_name("nuclear_safety.db")))
READING_TYPES = (
    "Radiation Dose (mSv)",
    "Coolant Temperature (°C)",
    "Pressure (bar)",
)


class SafetyDatabase:
    """Own the schema and all parameterized database operations."""

    def __init__(self, path: Path | str = DB_PATH) -> None:
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self._create_schema()
        self._seed_if_completely_empty()

    @contextmanager
    def transaction(self):
        try:
            yield self.connection
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise

    def _create_schema(self) -> None:
        with self.transaction() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS plants (
                    plant_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    plant_name TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    safety_officer_email TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS reactor_units (
                    unit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    plant_id INTEGER NOT NULL,
                    unit_identifier TEXT NOT NULL,
                    commissioning_date TEXT NOT NULL,
                    FOREIGN KEY (plant_id) REFERENCES plants(plant_id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS safety_readings (
                    reading_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    unit_id INTEGER NOT NULL,
                    reading_type TEXT NOT NULL,
                    measured_value REAL NOT NULL CHECK (measured_value >= 0),
                    FOREIGN KEY (unit_id) REFERENCES reactor_units(unit_id) ON DELETE CASCADE
                );
                """
            )

    def _seed_if_completely_empty(self) -> None:
        counts = [self.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                  for table in ("plants", "reactor_units", "safety_readings")]
        if any(counts):
            return
        samples = (
            ("Northstar Nuclear Station", "safety@northstar.example", "Unit-2 – PWR", "2018-06-15",
             "Radiation Dose (mSv)", 0.12),
            ("Riverside Energy Plant", "officer@riverside.example", "Unit-4 – BWR", "2021-09-01",
             "Coolant Temperature (°C)", 286.4),
        )
        with self.transaction() as conn:
            for plant, email, identifier, commissioned, reading_type, value in samples:
                cur = conn.execute(
                    "INSERT INTO plants (plant_name, safety_officer_email) VALUES (?, ?)", (plant, email)
                )
                unit = conn.execute(
                    "INSERT INTO reactor_units (plant_id, unit_identifier, commissioning_date) VALUES (?, ?, ?)",
                    (cur.lastrowid, identifier, commissioned),
                )
                conn.execute(
                    "INSERT INTO safety_readings (unit_id, reading_type, measured_value) VALUES (?, ?, ?)",
                    (unit.lastrowid, reading_type, value),
                )

    def add_record(self, plant_name: str, email: str, unit_identifier: str,
                   reading_type: str, measured_value: float, commissioned: str) -> None:
        with self.transaction() as conn:
            conn.execute(
                "INSERT INTO plants (plant_name, safety_officer_email) VALUES (?, ?) "
                "ON CONFLICT(plant_name) DO NOTHING", (plant_name, email)
            )
            plant = conn.execute("SELECT plant_id FROM plants WHERE plant_name = ? COLLATE NOCASE",
                                 (plant_name,)).fetchone()
            if plant is None:
                raise RuntimeError("Could not find or create the selected plant.")
            unit = conn.execute(
                "INSERT INTO reactor_units (plant_id, unit_identifier, commissioning_date) VALUES (?, ?, ?)",
                (plant["plant_id"], unit_identifier, commissioned),
            )
            conn.execute(
                "INSERT INTO safety_readings (unit_id, reading_type, measured_value) VALUES (?, ?, ?)",
                (unit.lastrowid, reading_type, measured_value),
            )

    def rows(self, table: str) -> list[sqlite3.Row]:
        if table not in {"plants", "reactor_units", "safety_readings"}:
            raise ValueError("Unknown table")
        return list(self.connection.execute(f"SELECT * FROM {table} ORDER BY 1"))

    def joined_rows(self) -> list[sqlite3.Row]:
        return list(self.connection.execute(
            """SELECT u.unit_id, p.plant_name, u.unit_identifier,
                      u.commissioning_date, s.reading_type, s.measured_value
               FROM reactor_units AS u
               JOIN plants AS p ON p.plant_id = u.plant_id
               JOIN safety_readings AS s ON s.unit_id = u.unit_id
               ORDER BY u.unit_id, s.reading_id"""
        ))

    def choices(self, entity: str) -> list[tuple[int, str]]:
        queries = {
            "plant": ("SELECT plant_id, plant_name FROM plants ORDER BY plant_name", "plant_id"),
            "unit": ("SELECT u.unit_id, p.plant_name || ' / ' || u.unit_identifier "
                     "FROM reactor_units u JOIN plants p USING (plant_id) ORDER BY u.unit_id", "unit_id"),
            "reading": ("SELECT s.reading_id, p.plant_name || ' / ' || u.unit_identifier || ' / ' || "
                        "s.reading_type || ' = ' || s.measured_value FROM safety_readings s "
                        "JOIN reactor_units u USING (unit_id) JOIN plants p USING (plant_id) ORDER BY s.reading_id",
                        "reading_id"),
        }
        sql, _ = queries[entity]
        return [(int(row[0]), str(row[1])) for row in self.connection.execute(sql)]

    def delete(self, entity: str, record_id: int) -> None:
        table, key = {"plant": ("plants", "plant_id"), "unit": ("reactor_units", "unit_id"),
                      "reading": ("safety_readings", "reading_id")}[entity]
        with self.transaction() as conn:
            conn.execute(f"DELETE FROM {table} WHERE {key} = ?", (record_id,))

    def close(self) -> None:
        self.connection.close()


def _in_notebook() -> bool:
    try:
        from IPython import get_ipython  # type: ignore
        shell = get_ipython()
        return shell is not None and shell.__class__.__name__ in {"ZMQInteractiveShell", "Shell"}
    except Exception:
        return False


class NotebookDashboard:
    def __init__(self, db: SafetyDatabase) -> None:
        import ipywidgets as widgets
        from IPython.display import display
        self.w, self.display, self.db = widgets, display, db
        self.status = widgets.HTML(value="<span style='color:#64748b'>Ready when you are.</span>")
        input_layout = widgets.Layout(width="100%", margin="3px 0 7px 0")
        self.plant = widgets.Text(description="Plant", placeholder="e.g. Lakeside Station", style={"description_width": "115px"}, layout=input_layout)
        self.email = widgets.Text(description="Officer email", placeholder="safety@example.org", style={"description_width": "115px"}, layout=input_layout)
        self.unit = widgets.Text(description="Unit", placeholder="e.g. Unit-2 – PWR", style={"description_width": "115px"}, layout=input_layout)
        self.commissioned = widgets.Text(description="Commissioned", value=date.today().isoformat(), style={"description_width": "115px"}, layout=input_layout)
        self.kind = widgets.Dropdown(description="Reading type", options=READING_TYPES, style={"description_width": "115px"}, layout=input_layout)
        self.value = widgets.Text(description="Measured value", placeholder="0 or greater", style={"description_width": "115px"}, layout=input_layout)
        self.add_button = widgets.Button(description="Add Record", button_style="success", icon="plus", layout=widgets.Layout(width="100%", margin="8px 0 0 0"))
        self.add_button.on_click(self._add)
        self.delete_entity = widgets.Dropdown(description="Record type", style={"description_width": "90px"}, layout=input_layout, options=[("Safety reading", "reading"),
            ("Reactor unit (cascades readings)", "unit"), ("Nuclear plant (cascades all)", "plant")])
        self.delete_choice = widgets.Dropdown(description="Record", options=[], style={"description_width": "90px"}, layout=input_layout)
        self.delete_button = widgets.Button(description="Delete Selected", button_style="danger", icon="trash", layout=widgets.Layout(width="100%", margin="8px 0 0 0"))
        self.delete_entity.observe(self._refresh_delete_choices, names="value")
        self.delete_button.on_click(self._delete)
        self.tabs = widgets.Tab(children=[widgets.Output() for _ in range(4)])
        for index, title in enumerate(("Joined view", "Plants", "Reactor units", "Safety readings")):
            self.tabs.set_title(index, title)
        self.refresh()

    def show(self) -> None:
        w = self.w
        insert = w.VBox([w.HTML("<div class='card-title'>Log a new reading</div><div class='card-note'>A plant, reactor unit, and safety reading are saved together.</div>"), self.plant, self.email,
                         self.unit, self.commissioned, self.kind, self.value, self.add_button])
        delete = w.VBox([w.HTML("<div class='card-title'>Manage records</div><div class='card-note'>Choose a record to remove. Parent deletions cascade to children.</div>"), self.delete_entity, self.delete_choice,
                         self.delete_button, w.HTML("<div class='delete-note'>Deleting a plant removes its units and readings. Deleting a unit removes its readings.</div>")])
        for card in (insert, delete):
            card.layout = w.Layout(width="50%", padding="18px", border="1px solid #dbe4ee",
                                   border_radius="12px", background_color="#ffffff")
        self.metric_cards = w.HTML()
        hero = w.HTML(f"""<div style='background:linear-gradient(115deg,#10243a,#17445a);padding:24px 28px;border-radius:16px;color:#fff;margin-bottom:16px'>
          <div style='font-size:12px;letter-spacing:2px;text-transform:uppercase;color:#67e8c0;font-weight:700'>Operations · Safety intelligence</div>
          <div style='font-size:28px;font-weight:750;margin:5px 0'>{APP_TITLE}</div>
          <div style='color:#c6d5e0;font-size:14px'>A live overview of plants, reactor units, and monitored readings.</div></div>""")
        self.display(w.VBox([w.HTML("""<style>
          .card-title{font-size:17px;font-weight:700;color:#142d43;margin:0 0 4px}
          .card-note{font-size:12px;color:#64748b;margin:0 0 14px}
          .delete-note{font-size:11px;color:#64748b;line-height:1.5;margin-top:10px}
          .widget-label{color:#334155}
        </style>"""), hero, self.metric_cards,
          w.HBox([insert, delete], layout=w.Layout(align_items="stretch", gap="14px", margin="10px 0 14px")),
          self.status, self.tabs], layout=w.Layout(width="100%")))

    def _refresh_delete_choices(self, _change: Any = None) -> None:
        entity = self.delete_entity.value
        self.delete_choice.options = [(f"{label} (ID {key})", key) for key, label in self.db.choices(entity)]
        if self.delete_choice.options:
            self.delete_choice.value = self.delete_choice.options[0][1]

    def _add(self, _button: Any) -> None:
        fields = [self.plant.value.strip(), self.email.value.strip(), self.unit.value.strip(), self.value.value.strip()]
        if not all(fields) or not self.commissioned.value.strip():
            self.status.value = "<span style='color:#a33'>Fill in all fields.</span>"; return
        try:
            value = float(self.value.value)
            if value < 0: raise ValueError
            date.fromisoformat(self.commissioned.value.strip())
            self.db.add_record(fields[0], fields[1], fields[2], self.kind.value, value,
                               self.commissioned.value.strip())
        except ValueError:
            self.status.value = "<span style='color:#a33'>Enter a non-negative number and a valid date (YYYY-MM-DD).</span>"; return
        except sqlite3.Error as exc:
            self.status.value = f"<span style='color:#a33'>Database error: {exc}</span>"; return
        for field in (self.plant, self.email, self.unit, self.value): field.value = ""
        self.commissioned.value = date.today().isoformat()
        self.refresh()
        self.status.value = "<span style='color:green'>Record added.</span>"

    def _delete(self, _button: Any) -> None:
        selected = self.delete_choice.value
        if selected is None:
            self.status.value = "<span style='color:#a33'>There are no records of this type to delete.</span>"; return
        self.db.delete(self.delete_entity.value, int(selected))
        self.refresh()
        self.status.value = "<span style='color:green'>Selected record deleted.</span>"

    def refresh(self) -> None:
        headers = (("Unit ID", "Plant Name", "Unit Identifier", "Commissioning Date", "Reading Type", "Measured Value"),
                   ("plant_id", "plant_name", "safety_officer_email"),
                   ("unit_id", "plant_id", "unit_identifier", "commissioning_date"),
                   ("reading_id", "unit_id", "reading_type", "measured_value"))
        datasets = (self.db.joined_rows(), self.db.rows("plants"), self.db.rows("reactor_units"),
                    self.db.rows("safety_readings"))
        totals = (len(datasets[1]), len(datasets[2]), len(datasets[3]))
        self.metric_cards.value = "<div style='display:flex;gap:10px;margin:0 0 12px'>" + "".join(
            f"<div style='flex:1;background:#fff;border:1px solid #dbe4ee;border-radius:11px;padding:12px 16px'>"
            f"<div style='font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:1px'>{label}</div>"
            f"<div style='font-size:24px;font-weight:750;color:#12304a'>{count}</div></div>"
            for label, count in zip(("Nuclear plants", "Reactor units", "Safety readings"), totals)) + "</div>"
        for output, columns, rows in zip(self.tabs.children, headers, datasets):
            with output:
                output.clear_output(wait=True)
                self.display(self.w.HTML(self._table(columns, rows)))
        self._refresh_delete_choices()

    @staticmethod
    def _table(columns: tuple[str, ...], rows: list[Any]) -> str:
        esc = __import__("html").escape
        head = "".join(f"<th>{esc(str(c))}</th>" for c in columns)
        body = "".join("<tr>" + "".join(f"<td>{esc(str(v))}</td>" for v in row) + "</tr>" for row in rows)
        if not body: body = f"<tr><td colspan='{len(columns)}'>No records</td></tr>"
        return ("<div style='overflow-x:auto;background:#fff;border:1px solid #dbe4ee;border-radius:10px;padding:4px'>"
                "<table style='border-collapse:collapse;width:100%;font:13px system-ui,Segoe UI,sans-serif;color:#26394b'>"
                f"<thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>"
                "<style>th,td{padding:10px 12px;border-bottom:1px solid #e8edf2;text-align:left}"
                "th{background:#f3f7fa;color:#456078;font-size:11px;text-transform:uppercase;letter-spacing:.5px}"
                "tbody tr:nth-child(even){background:#f8fafc}</style>")


class TkDashboard:
    """Desktop UI built around ttk widgets; database logic lives in SafetyDatabase."""
    def __init__(self, root: Any, db: SafetyDatabase) -> None:
        import tkinter as tk
        from tkinter import ttk
        self.tk, self.ttk, self.root, self.db = tk, ttk, root, db
        root.title(APP_TITLE); root.geometry("1180x820"); root.minsize(900, 680)
        root.configure(background="#f2f5f8")
        style = ttk.Style(root)
        try: style.theme_use("clam")
        except tk.TclError: pass
        style.configure("TFrame", background="#f2f5f8")
        style.configure("TLabel", background="#ffffff", foreground="#26394b", font=("Segoe UI", 9))
        style.configure("TLabelframe", background="#ffffff", bordercolor="#dbe4ec", relief="solid")
        style.configure("TLabelframe.Label", background="#ffffff", foreground="#16334a", font=("Segoe UI", 10, "bold"))
        style.configure("TButton", font=("Segoe UI", 9, "bold"), padding=(10, 7), background="#146c68", foreground="#ffffff")
        style.map("TButton", background=[("active", "#0d5754")], foreground=[("disabled", "#94a3b8")])
        style.configure("TEntry", padding=6, fieldbackground="#fbfdff")
        style.configure("TCombobox", padding=6, fieldbackground="#fbfdff")
        style.configure("Treeview", background="#ffffff", fieldbackground="#ffffff", foreground="#26394b",
                        rowheight=29, font=("Segoe UI", 9), borderwidth=0)
        style.configure("Treeview.Heading", background="#eaf0f5", foreground="#3b566d",
                        font=("Segoe UI", 8, "bold"), padding=(9, 8), relief="flat")
        style.map("Treeview", background=[("selected", "#d9f1ed")], foreground=[("selected", "#163d40")])
        style.configure("TNotebook", background="#f2f5f8", borderwidth=0)
        style.configure("TNotebook.Tab", background="#e5ebf0", foreground="#52677a", padding=(15, 9), font=("Segoe UI", 9, "bold"))
        style.map("TNotebook.Tab", background=[("selected", "#ffffff")], foreground=[("selected", "#146c68")])

        self.status = tk.StringVar(value="Ready · Database connected")
        hero = tk.Frame(root, bg="#102a40", padx=24, pady=18)
        hero.pack(fill="x")
        tk.Label(hero, text="OPERATIONS  /  SAFETY INTELLIGENCE", bg="#102a40", fg="#6ce0bd",
                 font=("Segoe UI", 8, "bold")).pack(anchor="w")
        tk.Label(hero, text=APP_TITLE, bg="#102a40", fg="#ffffff",
                 font=("Segoe UI", 19, "bold")).pack(anchor="w", pady=(3, 1))
        tk.Label(hero, text="A live overview of plants, reactor units, and monitored readings.",
                 bg="#102a40", fg="#c2d2df", font=("Segoe UI", 9)).pack(anchor="w")

        self.metric_values = [tk.StringVar(value="0") for _ in range(3)]
        metrics = tk.Frame(root, bg="#f2f5f8", padx=16, pady=12)
        metrics.pack(fill="x")
        for index, (title, var, accent) in enumerate(zip(("NUCLEAR PLANTS", "REACTOR UNITS", "SAFETY READINGS"),
                                                         self.metric_values, ("#146c68", "#3276a8", "#b87820"))):
            card = tk.Frame(metrics, bg="#ffffff", highlightbackground="#dbe4ec", highlightthickness=1, padx=14, pady=9)
            card.pack(side="left", fill="x", expand=True, padx=(0 if index == 0 else 8, 0))
            tk.Label(card, text=title, bg="#ffffff", fg="#718195", font=("Segoe UI", 8, "bold")).pack(anchor="w")
            tk.Label(card, textvariable=var, bg="#ffffff", fg=accent, font=("Segoe UI", 18, "bold")).pack(anchor="w")

        top = ttk.Frame(root, padding=(16, 0, 16, 8)); top.pack(fill="x")
        insert = ttk.LabelFrame(top, text="  LOG A NEW READING  ", padding=11)
        delete = ttk.LabelFrame(top, text="  MANAGE RECORDS  ", padding=11)
        insert.pack(side="left", fill="x", expand=True, padx=(0, 10)); delete.pack(side="left", fill="x")
        self.vars = {name: tk.StringVar() for name in ("plant", "email", "unit", "date", "value")}
        self.vars["date"].set(date.today().isoformat())
        fields = [("Plant name", "plant"), ("Safety officer email", "email"),
                  ("Unit identifier", "unit"), ("Commissioning date (YYYY-MM-DD)", "date"),
                  ("Measured value", "value")]
        for row, (label, key) in enumerate(fields):
            ttk.Label(insert, text=label).grid(row=row, column=0, sticky="w", padx=4, pady=3)
            ttk.Entry(insert, textvariable=self.vars[key], width=34).grid(row=row, column=1, sticky="ew", padx=4, pady=3)
        ttk.Label(insert, text="Reading type").grid(row=5, column=0, sticky="w", padx=4, pady=3)
        self.kind = ttk.Combobox(insert, values=READING_TYPES, state="readonly", width=31); self.kind.current(0)
        self.kind.grid(row=5, column=1, sticky="ew", padx=4, pady=3)
        ttk.Button(insert, text="＋  Add Record", command=self.add).grid(row=6, column=0, columnspan=2, sticky="ew", pady=7)
        insert.columnconfigure(1, weight=1)
        ttk.Label(delete, text="Record type").grid(row=0, column=0, sticky="w", pady=3)
        self.entity = ttk.Combobox(delete, state="readonly", values=("Safety reading", "Reactor unit", "Nuclear plant"), width=27)
        self.entity.current(0); self.entity.grid(row=1, column=0, sticky="ew", pady=3); self.entity.bind("<<ComboboxSelected>>", self.refresh_choices)
        ttk.Label(delete, text="Record").grid(row=2, column=0, sticky="w", pady=3)
        self.choice = ttk.Combobox(delete, state="readonly", width=37); self.choice.grid(row=3, column=0, sticky="ew", pady=3)
        ttk.Button(delete, text="⌫  Delete Selected", command=self.delete).grid(row=4, column=0, sticky="ew", pady=7)
        ttk.Label(delete, text="Plant and unit deletions cascade to their child records.", wraplength=250).grid(row=5, column=0, sticky="w")
        statusbar = tk.Frame(root, bg="#e8eef3", padx=18, pady=7)
        statusbar.pack(fill="x", padx=16, pady=(0, 7))
        tk.Label(statusbar, textvariable=self.status, bg="#e8eef3", fg="#52677a", font=("Segoe UI", 9)).pack(anchor="w")
        self.tabs = ttk.Notebook(root); self.tabs.pack(fill="both", expand=True, padx=16, pady=(0, 14))
        self.views = []
        for title in ("Joined view", "Plants", "Reactor units", "Safety readings"):
            frame = ttk.Frame(self.tabs); self.tabs.add(frame, text=title)
            frame.configure(style="TFrame")
            tree = ttk.Treeview(frame, show="headings"); y = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
            x = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview); tree.configure(yscrollcommand=y.set, xscrollcommand=x.set)
            tree.grid(row=0, column=0, sticky="nsew"); y.grid(row=0, column=1, sticky="ns"); x.grid(row=1, column=0, sticky="ew")
            frame.rowconfigure(0, weight=1); frame.columnconfigure(0, weight=1); self.views.append(tree)
        self.refresh()
        root.protocol("WM_DELETE_WINDOW", self.close)

    def refresh_choices(self, _event: Any = None) -> None:
        entity = {"Safety reading": "reading", "Reactor unit": "unit", "Nuclear plant": "plant"}[self.entity.get()]
        self.choice_map = self.db.choices(entity)
        self.choice["values"] = [f"{label} (ID {key})" for key, label in self.choice_map]
        self.choice.current(0 if self.choice_map else -1)

    def refresh(self) -> None:
        headers = (("Unit ID", "Plant Name", "Unit Identifier", "Commissioning Date", "Reading Type", "Measured Value"),
                   ("plant_id", "plant_name", "safety_officer_email"),
                   ("unit_id", "plant_id", "unit_identifier", "commissioning_date"),
                   ("reading_id", "unit_id", "reading_type", "measured_value"))
        rows = (self.db.joined_rows(), self.db.rows("plants"), self.db.rows("reactor_units"), self.db.rows("safety_readings"))
        for metric, records in zip(self.metric_values, rows[1:]): metric.set(str(len(records)))
        for tree, columns, records in zip(self.views, headers, rows):
            tree.delete(*tree.get_children()); tree["columns"] = columns
            for col in columns: tree.heading(col, text=col); tree.column(col, width=max(110, min(230, len(col) * 10)), anchor="w")
            for index, record in enumerate(records): tree.insert("", "end", values=tuple(record), tags=("odd" if index % 2 else "even",))
            tree.tag_configure("even", background="#ffffff")
            tree.tag_configure("odd", background="#f5f8fb")
        self.refresh_choices()

    def add(self) -> None:
        values = [self.vars[k].get().strip() for k in ("plant", "email", "unit", "date", "value")]
        if not all(values): self.status.set("Please fill in every field."); return
        try:
            measured = float(values[4])
            if measured < 0: raise ValueError
            date.fromisoformat(values[3])
            self.db.add_record(values[0], values[1], values[2], self.kind.get(), measured, values[3])
        except ValueError: self.status.set("Measured value must be numeric and non-negative; date must be YYYY-MM-DD."); return
        except sqlite3.Error as exc: self.status.set(f"Database error: {exc}"); return
        for var in self.vars.values(): var.set("")
        self.vars["date"].set(date.today().isoformat()); self.kind.current(0)
        self.refresh(); self.status.set("Record added.")

    def delete(self) -> None:
        index = self.choice.current()
        if index < 0: self.status.set("There are no records of this type to delete."); return
        entity = {"Safety reading": "reading", "Reactor unit": "unit", "Nuclear plant": "plant"}[self.entity.get()]
        self.db.delete(entity, self.choice_map[index][0]); self.refresh(); self.status.set("Selected record deleted.")

    def close(self) -> None:
        self.db.close(); self.root.destroy()


def main() -> None:
    db = SafetyDatabase()
    if _in_notebook():
        try:
            app = NotebookDashboard(db)
        except ImportError as exc:
            db.close()
            raise RuntimeError("Notebook mode requires ipywidgets. Install it with: pip install ipywidgets") from exc
        app.show()
    else:
        try:
            import tkinter as tk
        except ImportError as exc:
            db.close()
            raise RuntimeError("Tkinter is unavailable. Run this file in Jupyter/Colab with ipywidgets installed.") from exc
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            db.close()
            raise RuntimeError("No desktop display is available. In notebooks, run this file in the notebook kernel.") from exc
        TkDashboard(root, db)
        root.mainloop()


if __name__ == "__main__":
    main()
