import tkinter as tk
from tkinter import messagebox, filedialog
from tkinter.scrolledtext import ScrolledText
from pathlib import Path

class SimpleTextPad(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("TextPad — Untitled")
        self.geometry("800x600")

        # State
        self.current_path: Path | None = None
        self._dirty = False  # tracks unsaved edits

        # Widgets
        self.text = ScrolledText(self, wrap=tk.WORD, undo=True)
        self.text.pack(fill=tk.BOTH, expand=True, padx=8, pady=(8, 0))

        btnbar = tk.Frame(self)
        btnbar.pack(fill=tk.X, padx=8, pady=8)

        tk.Button(btnbar, text="Save",  width=10, command=self.save).pack(side=tk.LEFT, padx=(0, 6))
        tk.Button(btnbar, text="Load",  width=10, command=self.load_).pack(side=tk.LEFT, padx=6)
        tk.Button(btnbar, text="Clear", width=10, command=self.clear).pack(side=tk.LEFT, padx=6)
        tk.Button(btnbar, text="Exit",  width=10, command=self.on_exit).pack(side=tk.RIGHT)

        # Shortcuts
        self.bind_all("<Control-s>", lambda e: self.save())
        self.bind_all("<Control-o>", lambda e: self.load_())
        self.bind_all("<Control-n>", lambda e: self.clear())

        # Track modifications
        self.text.bind("<<Modified>>", self._on_modified)

        # Nice initial focus
        self.after(50, lambda: self.text.focus_set())

        # Intercept window close to warn on unsaved changes
        self.protocol("WM_DELETE_WINDOW", self.on_exit)

    # --- helpers -------------------------------------------------------------

    def _set_title(self, path: Path | None):
        name = path.name if path else "Untitled"
        dirty = " •" if self._dirty else ""
        self.title(f"TextPad — {name}{dirty}")

    def _get_text(self) -> str:
        # 'end-1c' avoids the trailing newline Tk adds
        return self.text.get("1.0", "end-1c")

    def _confirm_discard_if_dirty(self) -> bool:
        if not self._dirty:
            return True
        return messagebox.askyesno(
            "Unsaved changes",
            "You have unsaved changes. Discard them?",
            icon=messagebox.WARNING
        )

    def _on_modified(self, _evt=None):
        # Tk toggles the modified flag internally; we reset it after reading
        self._dirty = True
        self._set_title(self.current_path)
        self.text.edit_modified(False)

    # --- actions -------------------------------------------------------------

    def save(self):
        if self.current_path is None:
            path_str = filedialog.asksaveasfilename(
                title="Save text",
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
            )
            if not path_str:  # user cancelled
                return
            self.current_path = Path(path_str)

        try:
            # Ensure folder exists
            self.current_path.parent.mkdir(parents=True, exist_ok=True)
            # Write file
            self.current_path.write_text(self._get_text(), encoding="utf-8", newline="\n")
            self._dirty = False
            self._set_title(self.current_path)
            messagebox.showinfo("Saved", f"Saved to:\n{self.current_path}")
        except Exception as e:
            messagebox.showerror("Save failed", f"Could not save file.\n\n{e}")

    def load_(self):
        if not self._confirm_discard_if_dirty():
            return

        path_str = filedialog.askopenfilename(
            title="Load text",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if not path_str:
            return

        try:
            path = Path(path_str)
            text = path.read_text(encoding="utf-8")
            self.text.delete("1.0", tk.END)
            self.text.insert("1.0", text)
            self.current_path = path
            self._dirty = False
            self._set_title(self.current_path)
        except UnicodeDecodeError:
            messagebox.showerror("Load failed", "File is not valid UTF-8 text.")
        except Exception as e:
            messagebox.showerror("Load failed", f"Could not load file.\n\n{e}")

    def clear(self):
        if self._get_text() and not self._confirm_discard_if_dirty():
            return
        self.text.delete("1.0", tk.END)
        self.current_path = None
        self._dirty = False
        self._set_title(self.current_path)

    def on_exit(self):
        if self._dirty and not self._confirm_discard_if_dirty():
            return
        self.destroy()

if __name__ == "__main__":
    SimpleTextPad().mainloop()
