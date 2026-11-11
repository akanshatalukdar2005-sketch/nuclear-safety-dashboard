# Nuclear Safety Dashboard

A small SQLite-backed dashboard for recording nuclear plants, reactor units, and safety readings. The interface runs in a desktop Python environment with Tkinter or in Jupyter/Colab with `ipywidgets` installed.

## Run

```bash
python outputs/nuclear_safety_dashboard.py
```

In Jupyter or Colab, install `ipywidgets` if needed, then run the script from a cell:

```python
%run outputs/nuclear_safety_dashboard.py
```

The script creates `outputs/nuclear_safety.db` and seeds sample records when all three tables are empty. Set `NUCLEAR_DB_PATH` to use a different database location. SQLite foreign keys are enabled, with cascading deletes from plants to units and from units to readings.

## Features

- Add a plant, reactor unit, and reading in one submission.
- Delete readings independently or delete parent records with cascading cleanup.
- Browse a joined view and each of the three underlying tables.
- Validate required fields, non-negative numeric readings, and commissioning dates.

The Tkinter CRUD structure was informed by [w3resource's SQLite CRUD exercise](https://www.w3resource.com/python-exercises/tkinter/python-tkinter-file-operations-and-integration-exercise-12.php).
