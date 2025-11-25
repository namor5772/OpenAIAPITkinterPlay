import json
import sqlite3
from pathlib import Path
import tkinter as tk
from tkinter import messagebox
from tkinter import scrolledtext

# -------------------------
# Configuration
# -------------------------

# Path to the SQLite database
DB_PATH = Path(
    r"C:\Users\grobl\AppData\Local\Apps\2.0\A0WOLGB4.9YV\J81N8L7C.32C\diet..tion_0000000000000000_0002.0000_53548df2350299b6\foods.db"
    #r"C:\Users\roman\AppData\Local\Apps\2.0\47YPNLYJ.7QW\WVEC47TY.EC3\diet..tion_0000000000000000_0002.0000_39270b5535d9b46c\foods.db"
)

# Columns to insert (FoodId is autoincrement, so we omit it)
COLUMNS = [
    "FoodDescription",
    "Energy",
    "Protein",
    "FatTotal",
    "SaturatedFat",
    "TransFat",
    "PolyunsaturatedFat",
    "MonounsaturatedFat",
    "Carbohydrate",
    "Sugars",
    "DietaryFibre",
    "SodiumNa",
    "CalciumCa",
    "PotassiumK",
    "ThiaminB1",
    "RiboflavinB2",
    "NiacinB3",
    "Folate",
    "IronFe",
    "MagnesiumMg",
    "VitaminC",
    "Caffeine",
    "Cholesterol",
    "Alcohol",
]

# Extra keys that should be silently ignored (e.g. notes at the end)
IGNORED_EXTRA_KEYS = {"notes", "Notes"}


# -------------------------
# Database helper
# -------------------------

def insert_food_record(json_data: dict) -> int:
    """
    Insert a single food record into the Foods table.
    json_data must be a dict with keys exactly matching COLUMNS.
    Behaviour:
      - FoodDescription: if null -> empty string.
      - Any numeric field: if null or "null" -> 0.0
    Returns the auto-generated FoodId.
    """
    # Build the SQL INSERT statement dynamically
    column_list = ", ".join(COLUMNS)
    placeholders = ", ".join(["?"] * len(COLUMNS))
    sql = f"INSERT INTO Foods ({column_list}) VALUES ({placeholders})"

    values = []
    for col in COLUMNS:
        val = json_data.get(col, None)

        if col == "FoodDescription":
            # For description, allow None and treat as empty string
            if val is None:
                val = ""
            values.append(str(val))
        else:
            # For all numeric fields:
            # - If JSON has null -> Python None -> treat as 0.0
            # - If JSON has string "null" (case-insensitive) -> treat as 0.0
            if val is None:
                numeric_val = 0.0
            elif isinstance(val, str) and val.strip().lower() == "null":
                numeric_val = 0.0
            else:
                numeric_val = float(val)

            values.append(numeric_val)

    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute(sql, values)
        conn.commit()
        return cur.lastrowid  # type: ignore # The auto-generated FoodId
    finally:
        conn.close()


# -------------------------
# GUI Application
# -------------------------

class InsetNIPApp(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Insert NIP into foods.db")
        self.geometry("900x600")

        # Top instructions label
        label = tk.Label(
            self,
            text=(
                "Paste JSON for one food record into the box below, then click [Insert].\n"
                "The JSON must be a single object with keys matching the Foods table "
                "(excluding FoodId).\n"
                "A 'notes' field (if present) will be ignored. Any null numeric values "
                "are treated as 0.00."
            ),
            justify="left",
            anchor="w"
        )
        label.pack(fill="x", padx=10, pady=(10, 5))

        # Scrolled text box for JSON
        self.textbox = scrolledtext.ScrolledText(
            self,
            wrap=tk.WORD,
            font=("Consolas", 10),
        )
        self.textbox.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # Buttons frame
        button_frame = tk.Frame(self)
        button_frame.pack(fill="x", padx=10, pady=(0, 10))

        insert_button = tk.Button(
            button_frame,
            text="Insert",
            width=10,
            command=self.on_insert_clicked
        )
        insert_button.pack(side="left", padx=(0, 5))

        clear_button = tk.Button(
            button_frame,
            text="Clear",
            width=10,
            command=self.on_clear_clicked
        )
        clear_button.pack(side="left", padx=(0, 5))

        quit_button = tk.Button(
            button_frame,
            text="Quit",
            width=10,
            command=self.destroy
        )
        quit_button.pack(side="right")

    # ------------- Event handlers -------------

    def on_clear_clicked(self):
        """Clear the textbox contents."""
        self.textbox.delete("1.0", tk.END)

    def on_insert_clicked(self):
        """Parse the JSON from the textbox and insert into the database."""
        raw_text = self.textbox.get("1.0", tk.END).strip()

        if not raw_text:
            messagebox.showerror("Error", "Textbox is empty. Please paste JSON first.")
            return

        # Parse JSON
        try:
            data = json.loads(raw_text)
        except json.JSONDecodeError as e:
            messagebox.showerror(
                "JSON Error",
                f"Failed to parse JSON:\n{e}"
            )
            return

        # Must be a single object representing one row
        if not isinstance(data, dict):
            messagebox.showerror(
                "JSON Error",
                "Expected a single JSON object representing one food record."
            )
            return

        # Check for required keys (they must at least exist; values may be null)
        missing = [col for col in COLUMNS if col not in data]
        if missing:
            messagebox.showerror(
                "Validation Error",
                "The following required keys are missing:\n\n"
                + ", ".join(missing)
            )
            return

        # Compute extra keys, ignoring known harmless ones like "notes"
        extra = [
            k for k in data.keys()
            if (k not in COLUMNS and k not in IGNORED_EXTRA_KEYS)
        ]

        # If there are extra fields other than the ignored ones, warn the user
        if extra:
            proceed = messagebox.askyesno(
                "Extra fields detected",
                "The following keys are not used by the Foods table:\n\n"
                + ", ".join(extra)
                + "\n\nDo you want to ignore these and continue?"
            )
            if not proceed:
                return

        # Attempt to insert
        try:
            food_id = insert_food_record(data)
        except Exception as e:
            messagebox.showerror(
                "Database Error",
                f"Failed to insert record into database:\n{e}"
            )
            return

        messagebox.showinfo(
            "Success",
            f"Inserted food record successfully.\nNew FoodId = {food_id}"
        )


# -------------------------
# Main entry point
# -------------------------

if __name__ == "__main__":
    # Basic check for DB existence before starting GUI
    if not DB_PATH.exists():
        # Need a root window for messagebox in case DB missing
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "Database Not Found",
            f"Database file not found:\n{DB_PATH}"
        )
        root.destroy()
    else:
        app = InsetNIPApp()
        app.mainloop()
