"""
Minimal Tkinter + Streaming OpenAI Client
- Python 3.11+
- Tkinter mainloop kept responsive (thread + queue)
- Streaming via openai-python SDK
- Retries, timeouts, rotating logs
- JSON config persistence (model, temperature, system prompt, geometry)
- Rough token/cost estimate (editable pricing in config)
- Shortcuts: Ctrl+Enter=Send, Ctrl+S=Save Chat, Ctrl+L=Clear Input
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import os
import queue
import sys
import threading
import time
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

# --- OpenAI SDK (official) ---
# pip install --upgrade openai
from openai import OpenAI, DefaultHttpxClient  # type: ignore

# --- Logging --------------------------------------------------------------

def get_app_dir() -> Path:
    """Return per-user app data directory."""
    home = Path.home()
    if sys.platform.startswith("win"):
        base = Path(os.getenv("APPDATA", home / "AppData" / "Roaming"))
        return base / "MinimalTkOpenAI"
    elif sys.platform == "darwin":
        return home / "Library" / "Application Support" / "MinimalTkOpenAI"
    else:
        return home / ".minimal_tk_openai"

APP_DIR = get_app_dir()
LOG_DIR = APP_DIR / "logs"
CONFIG_PATH = APP_DIR / "config.json"
ENV_PATH = APP_DIR / ".env"

LOG_DIR.mkdir(parents=True, exist_ok=True)

from logging.handlers import RotatingFileHandler

logger = logging.getLogger("tk_openai")
logger.setLevel(logging.INFO)
handler = RotatingFileHandler(LOG_DIR / "app.log", maxBytes=512_000, backupCount=3)
formatter = logging.Formatter(
    "%(asctime)s | %(levelname)s | %(threadName)s | %(name)s | %(message)s"
)
handler.setFormatter(formatter)
logger.addHandler(handler)

# --- Config ---------------------------------------------------------------

DEFAULT_MODELS = [
    # Adjust as you like; ensure your account has access to chosen models.
    "gpt-4o-mini",
    "gpt-4o",
]

@dataclass
class Pricing:
    input_per_1k: float = 0.0  # USD per 1K input tokens
    output_per_1k: float = 0.0  # USD per 1K output tokens

@dataclass
class AppConfig:
    model: str = "gpt-4o-mini"
    temperature: float = 0.2
    system_prompt: str = "You are a helpful assistant."
    geometry: str | None = None
    prices: Dict[str, Pricing] = field(default_factory=dict)

    def to_json(self) -> str:
        d = asdict(self)
        # dataclass for Pricing -> dict
        d["prices"] = {k: asdict(v) for k, v in self.prices.items()}
        return json.dumps(d, indent=2)

    @staticmethod
    def from_json(s: str) -> "AppConfig":
        data = json.loads(s)
        prices = {
            k: Pricing(**v) if not isinstance(v, Pricing) else v
            for k, v in data.get("prices", {}).items()
        }
        return AppConfig(
            model=data.get("model", "gpt-4o-mini"),
            temperature=float(data.get("temperature", 0.2)),
            system_prompt=data.get("system_prompt", "You are a helpful assistant."),
            geometry=data.get("geometry"),
            prices=prices,
        )

def load_config() -> AppConfig:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    if CONFIG_PATH.exists():
        try:
            cfg = AppConfig.from_json(CONFIG_PATH.read_text(encoding="utf-8"))
            logger.info("Config loaded from %s", CONFIG_PATH)
            return cfg
        except Exception as exc:
            logger.exception("Failed to parse config: %s", exc)
    # Defaults; include a placeholder price mapping you can edit later.
    cfg = AppConfig(
        prices={
            # Example placeholders; set your own values to see estimates.
            # "gpt-4o-mini": Pricing(input_per_1k=0.0, output_per_1k=0.0),
        }
    )
    save_config(cfg)
    return cfg

def save_config(cfg: AppConfig) -> None:
    tmp = CONFIG_PATH.with_suffix(".json.tmp")
    tmp.write_text(cfg.to_json(), encoding="utf-8")
    tmp.replace(CONFIG_PATH)
    logger.info("Config saved to %s", CONFIG_PATH)

# --- Env / API key --------------------------------------------------------

def read_env_file(path: Path) -> Dict[str, str]:
    """Tiny .env reader; avoids extra dependencies."""
    if not path.exists():
        return {}
    values: Dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        values[k.strip()] = v.strip().strip('"').strip("'")
    return values

def load_api_key() -> Optional[str]:
    # Priority: environment > app .env > local .env beside script
    key = os.getenv("OPENAI_API_KEY")
    if key:
        return key
    vals = read_env_file(ENV_PATH)
    if "OPENAI_API_KEY" in vals:
        return vals["OPENAI_API_KEY"]
    local_env = Path(__file__).with_name(".env")
    vals2 = read_env_file(local_env)
    return vals2.get("OPENAI_API_KEY")

def mask_key(key: Optional[str]) -> str:
    if not key:
        return "<missing>"
    if len(key) <= 8:
        return "*" * len(key)
    return key[:4] + "*" * (len(key) - 8) + key[-4:]

# --- OpenAI Wrapper -------------------------------------------------------

def rough_token_count(text: str) -> int:
    """Very rough token estimate (~4 chars/token for English)."""
    if not text:
        return 0
    return max(1, math.ceil(len(text) / 4))

class OpenAIClientWrapper:
    """Thin wrapper with retries, timeout, and streaming support."""

    def __init__(self, api_key: str, timeout_s: float = 30.0, max_retries: int = 3):
        self._client = OpenAI(
            api_key=api_key,
            http_client=DefaultHttpxClient(timeout=timeout_s),  # official hook
        )
        self._max_retries = max_retries

    def stream_chat(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        temperature: float,
    ):
        """Generator yielding text chunks; raises on persistent failure."""
        delay = 1.0
        for attempt in range(1, self._max_retries + 1):
            try:
                stream = self._client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    stream=True,
                )
                for chunk in stream:
                    # SDK yields deltas; we only care about text
                    delta = chunk.choices[0].delta
                    piece = getattr(delta, "content", None)
                    if piece:
                        yield piece
                return
            except Exception as exc:
                # Backoff on transient network / rate-limit issues
                if attempt >= self._max_retries:
                    logger.exception("OpenAI error after %s attempts: %s", attempt, exc)
                    raise
                logger.warning(
                    "OpenAI error (attempt %s/%s): %s; retrying in %.1fs",
                    attempt, self._max_retries, exc, delay,
                )
                time.sleep(delay)
                delay = min(delay * 2, 8.0)

# --- Tkinter App ----------------------------------------------------------

class ChatApp(tk.Tk):
    def __init__(self, cfg: AppConfig, client: OpenAIClientWrapper):
        super().__init__()
        self.title("Minimal Tk + OpenAI (Streaming)")
        self.client = client
        self.cfg = cfg

        # State
        self.messages: List[Dict[str, Any]] = []
        self.stream_q: queue.Queue[Tuple[str, Any]] = queue.Queue()
        self.sending = False
        self.spinner_idx = 0
        self.spinner_frames = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

        # UI
        self._build_menu()
        self._build_main()
        self._apply_geometry()

        # Key bindings
        self.bind_all("<Control-Return>", lambda e: self.on_send())
        self.bind_all("<Control-Enter>", lambda e: self.on_send())
        self.bind_all("<Control-s>", lambda e: self.on_save_chat())
        self.bind_all("<Control-l>", lambda e: self.on_clear_input())

        # Initial system message
        if self.cfg.system_prompt.strip():
            self.messages.append({"role": "system", "content": self.cfg.system_prompt})

        self.after(100, self._poll_queue)
        self.after(120, self._tick_spinner)

    # --- UI builders ---
    def _build_menu(self) -> None:
        menubar = tk.Menu(self)
        filem = tk.Menu(menubar, tearoff=0)
        filem.add_command(label="Save Chat (Ctrl+S)", command=self.on_save_chat)
        filem.add_separator()
        filem.add_command(label="Reset to defaults", command=self.on_reset_config)
        filem.add_separator()
        filem.add_command(label="Exit", command=self.destroy)
        menubar.add_cascade(label="File", menu=filem)

        helpm = tk.Menu(menubar, tearoff=0)
        helpm.add_command(label="About", command=self.on_about)
        menubar.add_cascade(label="Help", menu=helpm)

        self.config(menu=menubar)

    def _build_main(self) -> None:
        root = ttk.Frame(self, padding=8)
        root.grid(row=0, column=0, sticky="nsew")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        # Top: controls
        controls = ttk.Frame(root)
        controls.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        controls.columnconfigure(4, weight=1)

        ttk.Label(controls, text="Model:").grid(row=0, column=0, sticky="w")
        self.model_var = tk.StringVar(value=self.cfg.model)
        self.model_cb = ttk.Combobox(
            controls, textvariable=self.model_var, values=DEFAULT_MODELS, width=18
        )
        self.model_cb.grid(row=0, column=1, padx=(4, 10))
        self.model_cb.bind("<<ComboboxSelected>>", lambda e: self._save_model())

        ttk.Label(controls, text="Temp:").grid(row=0, column=2, sticky="w")
        self.temp_var = tk.DoubleVar(value=self.cfg.temperature)
        self.temp_scale = ttk.Scale(
            controls, variable=self.temp_var, from_=0.0, to=1.0, command=self._save_temp
        )
        self.temp_scale.grid(row=0, column=3, sticky="ew", padx=(4, 10))

        self.btn_sys = ttk.Button(
            controls, text="Edit System Prompt", command=self.on_edit_system_prompt
        )
        self.btn_sys.grid(row=0, column=4, sticky="e")

        # Middle: transcript
        self.chat = tk.Text(
            root, wrap="word", height=20, state="disabled", undo=False
        )
        self.chat.grid(row=1, column=0, sticky="nsew")
        root.rowconfigure(1, weight=1)
        self.chat.tag_configure("role_user", foreground="#0b5394")      # blue
        self.chat.tag_configure("role_assistant", foreground="#38761d") # green
        self.chat.tag_configure("role_system", foreground="#6a1b9a")    # purple
        self.chat.tag_configure("meta", foreground="#888888", font=("TkDefaultFont", 8))

        # Bottom: input + buttons
        inputf = ttk.Frame(root)
        inputf.grid(row=2, column=0, sticky="ew", pady=(6, 0))
        inputf.columnconfigure(0, weight=1)

        self.input = tk.Text(inputf, height=3, wrap="word")
        self.input.grid(row=0, column=0, sticky="ew")
        self.input.focus_set()

        btns = ttk.Frame(inputf)
        btns.grid(row=0, column=1, padx=(6, 0), sticky="ns")
        self.btn_send = ttk.Button(btns, text="Send (Ctrl+Enter)", command=self.on_send)
        self.btn_send.grid(row=0, column=0, sticky="ew")
        self.btn_clear = ttk.Button(btns, text="Clear (Ctrl+L)", command=self.on_clear_input)
        self.btn_clear.grid(row=1, column=0, sticky="ew", pady=(4, 0))

        # Status bar
        self.status_var = tk.StringVar(value="Ready.")
        self.status = ttk.Label(root, textvariable=self.status_var, anchor="w")
        self.status.grid(row=3, column=0, sticky="ew", pady=(6, 0))

    # --- Utility ---
    def _apply_geometry(self) -> None:
        if self.cfg.geometry:
            self.geometry(self.cfg.geometry)
        else:
            self.geometry("860x640")
        self.minsize(700, 500)

    def _save_model(self) -> None:
        self.cfg.model = self.model_var.get().strip()
        save_config(self.cfg)

    def _save_temp(self, _evt: Any = None) -> None:
        self.cfg.temperature = float(self.temp_var.get())
        save_config(self.cfg)

    # --- Menu commands ---
    def on_about(self) -> None:
        messagebox.showinfo(
            "About",
            "Minimal Tk + OpenAI (Streaming)\n"
            "• Ctrl+Enter = Send\n"
            "• Ctrl+S = Save Chat\n"
            "• Ctrl+L = Clear Input\n"
            f"Config: {CONFIG_PATH}\n"
            f"Logs:   {LOG_DIR}\n"
            "Streamed via official OpenAI Python SDK.",
        )

    def on_reset_config(self) -> None:
        if not messagebox.askyesno("Reset", "Reset configuration to defaults?"):
            return
        self.cfg = AppConfig()
        save_config(self.cfg)
        self.model_var.set(self.cfg.model)
        self.temp_var.set(self.cfg.temperature)
        messagebox.showinfo("Reset", "Defaults restored.")

    def on_save_chat(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Save chat as",
            defaultextension=".txt",
            filetypes=[("Text", "*.txt"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            text = self.chat.get("1.0", "end-1c")
            Path(path).write_text(text, encoding="utf-8")
            self.set_status(f"Saved chat to {path}")
        except Exception as exc:
            logger.exception("Save failed: %s", exc)
            messagebox.showerror("Save failed", str(exc))

    def on_clear_input(self) -> None:
        self.input.delete("1.0", "end")

    def on_edit_system_prompt(self) -> None:
        dlg = tk.Toplevel(self)
        dlg.title("Edit System Prompt")
        dlg.transient(self)
        dlg.grab_set()
        dlg.geometry("640x300")

        txt = tk.Text(dlg, wrap="word")
        txt.pack(fill="both", expand=True, padx=8, pady=8)
        txt.insert("1.0", self.cfg.system_prompt)

        def save_and_close() -> None:
            self.cfg.system_prompt = txt.get("1.0", "end-1c")
            save_config(self.cfg)
            # Refresh system message in the active conversation if first message is system
            if self.messages and self.messages[0]["role"] == "system":
                self.messages[0]["content"] = self.cfg.system_prompt
            else:
                self.messages.insert(0, {"role": "system", "content": self.cfg.system_prompt})
            dlg.destroy()

        btn = ttk.Button(dlg, text="Save", command=save_and_close)
        btn.pack(pady=(0, 8))

    # --- Chat flow ---
    def on_send(self) -> None:
        if self.sending:
            return
        user_text = self.input.get("1.0", "end-1c").strip()
        if not user_text:
            return
        model = self.model_var.get().strip()
        temp = float(self.temp_var.get())

        self._append("user", user_text)
        self.input.delete("1.0", "end")

        self.messages.append({"role": "user", "content": user_text})
        self._start_stream(model, temp)

    def _start_stream(self, model: str, temp: float) -> None:
        self.sending = True
        self.btn_send.configure(state="disabled")
        self.set_status("Thinking… " + self.spinner_frames[self.spinner_idx])

        # Insert assistant header
        self._append("assistant", "", head_only=True)

        def worker():
            try:
                t0 = time.time()
                prompt_text = "".join(m.get("content", "") for m in self.messages)
                prompt_tokens = rough_token_count(prompt_text)
                out_accum: List[str] = []

                for piece in self.client.stream_chat(self.messages, model, temp):
                    out_accum.append(piece)
                    self.stream_q.put(("token", piece))

                output_text = "".join(out_accum)
                output_tokens = rough_token_count(output_text)
                dt = time.time() - t0

                self.stream_q.put((
                    "done",
                    {
                        "prompt_tokens": prompt_tokens,
                        "output_tokens": output_tokens,
                        "elapsed": dt,
                        "model": model,
                    },
                ))
            except Exception as exc:
                self.stream_q.put(("error", str(exc)))

        threading.Thread(target=worker, daemon=True, name="OpenAIWorker").start()

    # --- Queue / UI update loop ---
    def _poll_queue(self) -> None:
        try:
            while True:
                kind, payload = self.stream_q.get_nowait()
                if kind == "token":
                    self._append_stream_piece(payload)
                elif kind == "done":
                    self._finalize_assistant(payload)
                elif kind == "error":
                    self._handle_error(payload)
        except queue.Empty:
            pass
        finally:
            self.after(40, self._poll_queue)

    def _tick_spinner(self) -> None:
        if self.sending:
            self.spinner_idx = (self.spinner_idx + 1) % len(self.spinner_frames)
            self.set_status("Thinking… " + self.spinner_frames[self.spinner_idx])
        self.after(120, self._tick_spinner)

    def _append(self, role: str, text: str, head_only: bool = False) -> None:
        self.chat.configure(state="normal")
        if role == "user":
            self.chat.insert("end", "You: ", ("role_user",))
            self.chat.insert("end", text + "\n\n")
        elif role == "assistant":
            self.chat.insert("end", "Assistant: ", ("role_assistant",))
            if not head_only:
                self.chat.insert("end", text + "\n\n")
        elif role == "system":
            self.chat.insert("end", "System: ", ("role_system",))
            self.chat.insert("end", text + "\n\n")
        self.chat.see("end")
        self.chat.configure(state="disabled")

    def _append_stream_piece(self, piece: str) -> None:
        self.chat.configure(state="normal")
        self.chat.insert("end", piece)
        self.chat.see("end")
        self.chat.configure(state="disabled")

    def _finalize_assistant(self, meta: Dict[str, Any]) -> None:
        # Finish assistant line with spacing
        self.chat.configure(state="normal")
        self.chat.insert("end", "\n\n")
        self.chat.configure(state="disabled")

        # Add to message history
        last_assistant_text = self._get_last_assistant_block_text()
        self.messages.append({"role": "assistant", "content": last_assistant_text})

        # Update status with token/cost estimate
        prompt_t = int(meta.get("prompt_tokens", 0))
        output_t = int(meta.get("output_tokens", 0))
        model = str(meta.get("model", self.cfg.model))
        elapsed = float(meta.get("elapsed", 0.0))
        cost_str = self._estimate_cost_str(model, prompt_t, output_t)
        self.set_status(
            f"Done in {elapsed:.2f}s | tokens in/out: {prompt_t}/{output_t} | {cost_str}"
        )

        # Re-enable send
        self.sending = False
        self.btn_send.configure(state="normal")

    def _handle_error(self, msg: str) -> None:
        self.sending = False
        self.btn_send.configure(state="normal")
        logger.error("OpenAI error: %s", msg)
        messagebox.showerror("OpenAI error", msg)
        self.set_status("Error; see logs for details.")

    def _estimate_cost_str(self, model: str, t_in: int, t_out: int) -> str:
        pr = self.cfg.prices.get(model)
        if not pr or (pr.input_per_1k == 0.0 and pr.output_per_1k == 0.0):
            return "est. cost: n/a (set prices in config.json)"
        cost = (t_in / 1000) * pr.input_per_1k + (t_out / 1000) * pr.output_per_1k
        return f"est. cost: ${cost:.4f}"

    def _get_last_assistant_block_text(self) -> str:
        # Find the "Assistant:" label from the end and get following text until blank line
        text = self.chat.get("1.0", "end-1c")
        anchor = "Assistant: "
        idx = text.rfind(anchor)
        if idx == -1:
            return ""
        return text[idx + len(anchor):].rstrip()

    def set_status(self, msg: str) -> None:
        self.status_var.set(msg)

    # --- Closing / geometry ---
    def destroy(self) -> None:  # type: ignore[override]
        try:
            self.cfg.geometry = self.geometry()
            save_config(self.cfg)
        except Exception:
            pass
        super().destroy()

# --- Main -----------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Minimal Tk + OpenAI (Streaming)")
    parser.add_argument("--reset-config", action="store_true", help="Reset config and exit")
    parser.add_argument("--timeout", type=float, default=30.0, help="HTTP timeout (s)")
    args = parser.parse_args()

    if args.reset_config:
        CONFIG_PATH.unlink(missing_ok=True)
        print("Config reset. Relaunch the app.")
        return

    api_key = load_api_key()
    logger.info("Using OPENAI_API_KEY=%s", mask_key(api_key))
    if not api_key:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        if not ENV_PATH.exists():
            ENV_PATH.write_text("OPENAI_API_KEY=\n", encoding="utf-8")
        messagebox.showwarning(
            "Missing API key",
            "Set OPENAI_API_KEY in your environment or edit:\n"
            f"{ENV_PATH}\n\nThen restart the app.",
        )
        return

    cfg = load_config()
    try:
        client = OpenAIClientWrapper(api_key=api_key, timeout_s=args.timeout)
    except Exception as exc:
        logger.exception("Failed to init OpenAI client: %s", exc)
        messagebox.showerror("Init error", str(exc))
        return

    app = ChatApp(cfg, client)
    app.mainloop()

if __name__ == "__main__":
    main()
