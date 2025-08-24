import tkinter as tk
from tkinter import ttk, messagebox
from tkinter.scrolledtext import ScrolledText
from pathlib import Path
import json
import re

# -----------------------
# Layout constants (px)
# -----------------------
WINDOW_W = 870
WINDOW_H = 900

PADX = 10
PADY = 10

TEXT_X = 10
TEXT_Y = 70
TEXT_W = WINDOW_W - 20
TEXT_H = WINDOW_H - 80

STATE_FILE = ".textpadsimple_state.json"   # stored next to this .py file

class BasicTextPad(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Basic TextPad - https://github.com/namor5772/OpenAIAPITkinterPlay/blob/main/SimpleTextPad.py")
        self.geometry(f"{WINDOW_W}x{WINDOW_H}+0+0")

        # FIX: Create target dir where the program is RUN FROM (current working dir)
        # If you instead want the script's folder: Path(__file__).resolve().parent
        self.base_dir = (Path.cwd() / "system_prompts").resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

        # State file stored next to the script (not inside system_prompts)
        self.state_path = Path(__file__).resolve().parent / STATE_FILE

        # Tracks which base filename (stem) is currently loaded in the editor
        self.current_name: str | None = None

        # --- Widgets ---------------------------------------------------------
        self.lbl_name = tk.Label(self, text="Filename (no .txt):")
        self.lbl_name.place(x=PADX, y=PADY)

        self.var_filename = tk.StringVar()
        self.ent_name = tk.Entry(self, textvariable=self.var_filename)
        self.ent_name.place(x=115, y=PADY, width=260, height=26)

        self.btn_save = tk.Button(self, text="SAVE AS", command=self.save_as_clicked)
        self.btn_save.place(x=385, y=PADY, width=70, height=26)

        self.btn_clear = tk.Button(self, text="CLEAR", command=self.clear_all_reset)
        self.btn_clear.place(x=465, y=PADY, width=70, height=26)

        self.lbl_load = tk.Label(self, text="Load file:")
        self.lbl_load.place(x=540, y=PADY)

        self.var_choice = tk.StringVar()
        self.cbo_files = ttk.Combobox(self, textvariable=self.var_choice, state="readonly")
        self.cbo_files.place(x=595, y=PADY, width=260, height=26)
        self.cbo_files.bind("<Return>", self.load_selected)              # Enter loads
        self.cbo_files.bind("<<ComboboxSelected>>", self.load_selected)  # optional immediate load

        self.txt = ScrolledText(self, wrap=tk.WORD, undo=True)
        self.txt.place(x=TEXT_X, y=TEXT_Y, width=TEXT_W, height=TEXT_H)

        # Keyboard convenience
        self.bind_all("<Control-s>", self._accelerator_save)
        self.bind_all("<Control-S>", self._accelerator_save)

        # NEW: Ctrl+N → New (clear editor and reset state)
        self.bind_all("<Control-n>", self._accelerator_clear)
        self.bind_all("<Control-N>", self._accelerator_clear)

        # Populate combobox with existing .txt files (no extensions)
        self.refresh_combobox()

        # Try to restore last session (loads file, sets entry, selects/focuses combo)
        self.restore_state_or_focus_editor()

        # Intercept window close to persist state
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    # -----------------------
    # Helpers
    # -----------------------
    def list_txt_basenames(self):
        """Return a sorted list of filenames (without .txt) in base_dir."""
        return sorted(p.stem for p in self.base_dir.glob("*.txt"))

    def refresh_combobox(self):
        names = self.list_txt_basenames()
        self.cbo_files["values"] = names

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        """Constrain filename to safe characters."""
        name = name.strip()
        name = re.sub(r"[^A-Za-z0-9._ \-]", "_", name)
        name = re.sub(r"\s+", " ", name)
        return name

    def _select_combo_item(self, name: str):
        """Select 'name' in the combobox and focus it, if present."""
        values = list(self.cbo_files["values"])
        if name in values:
            self.cbo_files.current(values.index(name))
        self.cbo_files.focus_set()

    def _persist_state(self):
        """Save last loaded file stem (if any) to the state file."""
        data = {"last_file": self.current_name}
        try:
            self.state_path.write_text(json.dumps(data), encoding="utf-8")
        except Exception:
            pass  # non-fatal

    def _load_state(self):
        """Return last_file stem or None."""
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
            return data.get("last_file")
        except Exception:
            return None

    # -----------------------
    # Events / Commands
    # -----------------------
    def clear_all_reset(self):
        """
        Make [CLEAR] act like the original Ctrl+N:
        - Empty the ScrolledText
        - Clear the filename Entry
        - Deselect the Combobox (no selection text)
        - Forget the current file
        - Return focus to the editor
        """
        self.txt.delete("1.0", tk.END)   # empty editor
        self.var_filename.set("")        # clear filename Entry
        self.var_choice.set("")          # clear combobox variable text
        self.cbo_files.set("")           # ensure UI shows no selection
        self.current_name = None         # forget which file was 'open'
        self.txt.focus_set()             # caret back to editor

    def _accelerator_save(self, event=None):
        self.save_as_clicked()
        return "break"

    def _accelerator_clear(self, event=None):
        self.clear_all_reset()
        return "break"

    def save_as_clicked(self):
        raw = self.var_filename.get()
        name = self._sanitize_filename(raw)
        if not name:
            messagebox.showwarning("Missing name", "Please type a filename (without .txt).")
            self.ent_name.focus_set()
            return

        target = (self.base_dir / f"{name}.txt")
        text = self.txt.get("1.0", tk.END)  # keep trailing newline

        try:
            if target.exists():
                if not messagebox.askyesno(
                    "Overwrite?",
                    f"“{target.name}” already exists.\nDo you want to overwrite it?"
                ):
                    return
            target.write_text(text, encoding="utf-8")
        except Exception as e:
            messagebox.showerror("Save failed", f"Could not save file:\n{e}")
            return

        # Update combobox list if new
        current = list(self.cbo_files["values"])
        if name not in current:
            current.append(name)
            current.sort()
            self.cbo_files["values"] = current

        # Mark as the current open file
        self.current_name = name

        # Reflect in UI: select/focus combo and set entry
        self._select_combo_item(name)
        self.var_filename.set(name)

        messagebox.showinfo("Saved", f"Saved to:\n{target}")

    def load_selected(self, event=None):
        name = self.var_choice.get().strip()
        if not name:
            return
        path = self.base_dir / f"{name}.txt"
        if not path.exists():
            messagebox.showerror("Not found", f"File not found:\n{path}")
            return

        try:
            content = path.read_text(encoding="utf-8")
        except Exception as e:
            messagebox.showerror("Load failed", f"Could not read file:\n{e}")
            return

        self.txt.delete("1.0", tk.END)
        self.txt.insert(tk.END, content)

        # Update state/UI
        self.current_name = name
        self.var_filename.set(name)
        self._select_combo_item(name)
        # NOTE: Per your request, keep focus on the combobox after restore/load.

    def restore_state_or_focus_editor(self):
        """On startup, try to restore last file; else just show empty editor.
           Always give focus to the text area for immediate typing."""
        last = self._load_state()
        self.refresh_combobox()
        if last and (self.base_dir / f"{last}.txt").exists():
            # Select it in combo and load its content
            self.var_choice.set(last)
            self.load_selected()
        # Always focus the text area on startup
        self.txt.focus_set()

    def on_close(self):
        self._persist_state()
        self.destroy()

if __name__ == "__main__":
    app = BasicTextPad()
    app.mainloop()
