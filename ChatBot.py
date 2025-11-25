import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkinter.scrolledtext import ScrolledText
from pathlib import Path
import base64
import json
import re
import os
import mimetypes
from openai import OpenAI
import tiktoken
from typing import List, Dict, Any, Optional, Tuple, Set
import threading
try:
    from PIL import Image, ImageTk  # optional; used for nicer thumbnails if installed
except ImportError:
    Image = None
    ImageTk = None

# --- GUI Layout Constants ---
WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 950
WINDOW_W = 600
WINDOW_WIDTH_actual = WINDOW_WIDTH + WINDOW_W

PADX = WINDOW_WIDTH + 10
PADY = 10

TEXT_X = WINDOW_WIDTH + 10
TEXT_Y = 70
TEXT_W = WINDOW_W - 20
TEXT_H = WINDOW_HEIGHT - 80

STATE_FILE = ".textpad_state.json"   # stored next to this .py file
CHAT_AUTOSAVE_FILE = "_autosave.chat.json"   # lives in base_dir (system_prompts folder)

MODEL_CMB_X = 57
MODEL_CMB_Y = 10
MODEL_CMB_WIDTH = 180
MODEL_CMB_HEIGHT = 25

CHAT_DISPLAY_X = 10
CHAT_DISPLAY_Y = 45+5
CHAT_DISPLAY_WIDTH = WINDOW_WIDTH - 20
CHAT_DISPLAY_HEIGHT = WINDOW_HEIGHT - 140  # shorter to make room for the attachment bar and buttons

SOURCES_BUTTON_X = WINDOW_WIDTH - 90
SOURCES_BUTTON_Y = WINDOW_HEIGHT - (35+2)
SOURCES_BUTTON_WIDTH = 80
SOURCES_BUTTON_HEIGHT = 25

# Input/attachment row (numbers tuned to avoid overlap with Show sources)
ATTACH_BUTTON_X = 10
ATTACH_BUTTON_WIDTH = 96
ATTACH_BUTTON_HEIGHT = 28
ATTACH_BAR_HEIGHT = 32
INPUT_X = ATTACH_BUTTON_X + ATTACH_BUTTON_WIDTH + 12
INPUT_Y = WINDOW_HEIGHT - 35
SEND_BUTTON_WIDTH = 70
SEND_BUTTON_HEIGHT = 25
SEND_BUTTON_X = SOURCES_BUTTON_X - 8 - SEND_BUTTON_WIDTH
INPUT_WIDTH = SEND_BUTTON_X - 8 - INPUT_X
INPUT_HEIGHT = 25

SEND_BTN_LABEL = "Send"
SRC_BTN_LABEL = "Show sources"

# --- API Models related ---
ENABLE_HOSTED_WEB_SEARCH = True  # Turn this on to use the hosted web search tool
DEFAULT_MODEL = "" # Non-browsing model (or used without tools)
BROWSE_MODEL = "" # Browsing-capable model for hosted web search "gpt-4o"
MODEL_OPTIONS: List[str] = []
#str_system_prompt = "You are a helpful AI assistant. Answer questions to the best of your ability."

URL_REGEX = re.compile(
    r"(https?://[^\s)]+)",
    re.IGNORECASE
)

def _dedupe_preserve_order(items: List[str]) -> List[str]:
    seen: Set[str] = set()
    out: List[str] = []
    for it in items:
        if it not in seen:
            seen.add(it)
            out.append(it)
    return out


class ChatMemoryBot:
    def __init__(self, max_tokens: int = 30000):
        self.client = OpenAI()

        # Get all models intended for standard completions/chat into MODEL_OPTIONS array
        global MODEL_OPTIONS
        models = self.client.models.list()
        n = 0
        # Skip anything not intended for standard completions/chat
        for m in models.data:
            model_id = m.id
            if any(skip in model_id for skip in ["embedding", "audio", "search", "realtime", "preview","transcribe", "tts"]):
                continue
            if model_id.startswith("gpt-") and not("instruct" in model_id) and (model_id != "gpt-image-1"):
                MODEL_OPTIONS.append(model_id)
                n += 1
        print(f"\n=== {n} Chat Models (use /chat/completions) ===")
        n = 0
        MODEL_OPTIONS.sort()
        for cm in MODEL_OPTIONS: 
            n +=1
            print(f"{n}: {cm}")
        self.default_model = MODEL_OPTIONS[0]
        self.browse_model = MODEL_OPTIONS[0]
        self.max_tokens = max_tokens
        self.str_system_prompt = "You are a helpfull assistant"

        # tiktoken mapping with a safe fallback for new model names
        try:
            self.encoder = tiktoken.encoding_for_model(self.browse_model)
        except KeyError:
            print("EXCEPTION")
            prefers_long_ctx = any(s in self.browse_model for s in ("gpt-5", "4.1", "4o", "o4", "o3", "200k"))
            encoding_name = "o200k_base" if prefers_long_ctx else "cl100k_base"
            self.encoder = tiktoken.get_encoding(encoding_name)

        self.chat_history: List[Dict[str, str]] = [{"role": "system", "content": self.str_system_prompt}]
        print(f"System prompt:\n{self.chat_history}")


    def reset(self, system_prompt: Optional[str] = None) -> None:
        """
        Reset the conversation to a fresh state containing only the system message.
        If system_prompt is provided, it replaces the current system prompt and is used
        as the sole message in chat_history.
        """
        if system_prompt is None:
            system_prompt = self.str_system_prompt
        else:
            self.str_system_prompt = system_prompt

        self.chat_history = [{"role": "system", "content": self.str_system_prompt}]
        print("[Bot] Chat history reset to system-only state.")



    def _content_to_text(self, content: Any, include_placeholders: bool = False) -> str:
        """
        Extract only the textual parts of a message content payload.
        When include_placeholders is True, image parts contribute a short placeholder
        so token counting/logging stays lightweight.
        """
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: List[str] = []
            image_added = False
            for part in content:
                if not isinstance(part, dict):
                    continue
                p_type = part.get("type", "")
                if p_type in ("text", "input_text"):
                    parts.append(part.get("text", ""))
                elif include_placeholders and p_type in ("image_url", "input_image") and not image_added:
                    parts.append("[image attached]")
                    image_added = True
            return " ".join(p for p in parts if p)
        return ""


    def _normalize_messages_for_api(
        self,
        messages: List[Dict[str, Any]],
        include_images: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Convert chat_history entries into the structured format expected by the
        Responses API, optionally omitting image payloads (for summaries).
        """
        normalized: List[Dict[str, Any]] = []
        for msg in messages:
            role = msg.get("role", "user")
            raw_content = msg.get("content", "")
            parts: List[Dict[str, Any]] = []
            placeholder_added = False

            if isinstance(raw_content, str):
                parts.append({"type": "input_text", "text": raw_content})
            elif isinstance(raw_content, list):
                for part in raw_content:
                    if not isinstance(part, dict):
                        continue
                    p_type = part.get("type")
                    if p_type in ("text", "input_text"):
                        parts.append({"type": "input_text", "text": part.get("text", "")})
                    elif p_type in ("image_url", "input_image"):
                        image_val = part.get("image_url")
                        if include_images and image_val:
                            # Allow either direct string or {"url": ...} shapes.
                            if isinstance(image_val, dict) and "url" in image_val:
                                image_val = image_val["url"]
                            parts.append({"type": "input_image", "image_url": image_val})
                        elif (not include_images) and (not placeholder_added):
                            parts.append({"type": "input_text", "text": "[image omitted]"})
                            placeholder_added = True
            if not parts:
                parts.append({"type": "input_text", "text": str(raw_content)})

            normalized.append({"role": role, "content": parts})
        return normalized


    def _count_tokens(self, messages: List[Dict[str, Any]]) -> int:
        return sum(len(self.encoder.encode(self._content_to_text(msg.get("content", ""), include_placeholders=True))) for msg in messages)


    def _summarize_history(self, old_messages: List[Dict[str, Any]]) -> str:
        """
        Use the DEFAULT (non-browsing) model for summaries to avoid any tool usage.
        Images are stripped to placeholders so we do not inflate the prompt.
        """
        summary_prompt: List[Dict[str, Any]] = [
            {"role": "system", "content": [{"type": "input_text", "text": "Summarize the following chat history in ~500 words, neutral tone."}]}
        ] + self._normalize_messages_for_api(old_messages, include_images=False)

        resp = self.client.responses.create(
            model=self.default_model,  # default model; no tools
            input=summary_prompt, # type: ignore
        )
        return getattr(resp, "output_text", "") or ""


    def _trim_history_if_needed(self):
        token_count = self._count_tokens(self.chat_history)
        print(f"\nTOKEN COUNT = {token_count}")

        if token_count > self.max_tokens:
            system_msg = self.chat_history[0]
            old_messages = self.chat_history[1:-10]
            recent_messages = self.chat_history[-10:]
            print(f"\nTRIMMING HISTORY: {len(old_messages)} messages summarized to 1 message")

            summary = self._summarize_history(old_messages)
            print(f"\nSUMMARY START:\n{summary}\nSUMMARY END***")
            print(f"\nSUMMARY LENGTH (chars): {len(summary)}\n")

            # this is the new trimmed chat history
            self.chat_history = [
                system_msg,
                {"role": "assistant", "content": f"Summary of earlier conversation: {summary}"}
            ] + recent_messages


    # --- Robust citation extraction ---
    def _extract_citations(self, resp: Any, reply_text: str) -> List[str]:
        urls: List[str] = []

        # 1) Walk the structured response to find URL-like fields
        def walk(obj: Any):
            if isinstance(obj, dict):
                for k, v in obj.items(): # type: ignore
                    if k.lower() in ("url", "source", "href") and isinstance(v, str) and v.startswith(("http://", "https://")): # type: ignore
                        urls.append(v.strip())
                    walk(v)
            elif isinstance(obj, list):
                for it in obj: # type: ignore
                    walk(it)
            # primitives ignored

        try:
            raw = json.loads(json.dumps(resp, default=lambda o: getattr(o, "__dict__", str(o))))
            walk(raw)
        except Exception as e:
            print(f"[Citations] Structured parse fallback due to: {type(e).__name__}: {e}")

        # 2) Fallback: URLs present in the final text
        urls += URL_REGEX.findall(reply_text or "")

        # Clean + de-dupe
        cleaned = []
        for u in urls:
            u = u.rstrip(").,;:]").lstrip("([")
            cleaned.append(u) # type: ignore

        return _dedupe_preserve_order(cleaned) # type: ignore


    def _build_request(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Decide model and tool configuration based on ENABLE_HOSTED_WEB_SEARCH.
        Ensures tools are only sent with a browsing-capable model.
        """
        global ENABLE_HOSTED_WEB_SEARCH
        use_browsing = ENABLE_HOSTED_WEB_SEARCH
        if use_browsing:
            # Browsing flow: choose browsing model and include the hosted tool
            return {
                "model": self.browse_model,
                "input": messages,
                "tools": [{"type": "web_search"}],
                "tool_choice": "auto",
            }
        else:
            # Non-browsing flow: default model with NO tools
            return {
                "model": self.default_model,
                "input": messages,
            }


    def ask(self, user_input: str, attachments: Optional[List[Dict[str, str]]] = None) -> Tuple[str, List[str]]:
        print("\nASKING AI")

        # Obtain the system prompt string and create the message
        #global str_system_prompt
        self.str_system_prompt = app.txt.get("1.0", tk.END).strip()  # Get the system prompt from the text area
        self.chat_history[0] = {"role": "system", "content": self.str_system_prompt} # type: ignore
        print(f"System prompt:\n{self._content_to_text(self.chat_history[0].get('content', ''), include_placeholders=True)}")

        # Build the user message with optional images
        content_parts: List[Dict[str, Any]] = []
        if user_input:
            content_parts.append({"type": "input_text", "text": user_input})

        for att in attachments or []:
            data_url = att.get("data_url")
            if data_url:
                content_parts.append({"type": "input_image", "image_url": data_url})

        if content_parts:
            self.chat_history.append({"role": "user", "content": content_parts}) # type: ignore
        else:
            # Fallback to plain text slot to keep schema valid
            self.chat_history.append({"role": "user", "content": user_input})

        self._trim_history_if_needed()

        normalized_history = self._normalize_messages_for_api(self.chat_history, include_images=True)
        request_kwargs: Dict[str, Any] = self._build_request(normalized_history)

        # Primary attempt
        try:
            resp = self.client.responses.create(**request_kwargs) # type: ignore
        except Exception as e:
            # Graceful fallback if the error suggests tools/model incompatibility
            msg = str(e)
            if ("web_search" in msg or "web_search_preview" in msg or "tools" in msg) and "not supported" in msg.lower():
                print("[Warn] Tool/model mismatch detected. Retrying without tools on default_model.")
                fallback_kwargs = { # type: ignore
                    "model": self.default_model,
                    "input": self._normalize_messages_for_api(self.chat_history, include_images=True)
                }
                resp = self.client.responses.create(**fallback_kwargs) # type: ignore
            else:
                raise  # unrelated error

        reply = getattr(resp, "output_text", "") or "" # type: ignore
        sources = self._extract_citations(resp, reply)

        self.chat_history.append({"role": "assistant", "content": reply})
        def _log_line(msg: Any) -> str:
            if isinstance(msg, dict):
                return f"{msg.get('role', '?')}: {self._content_to_text(msg.get('content', ''), include_placeholders=True)}"
            return str(msg)
        print("\n".join(f"{idx:02d}: {_log_line(msg)}" for idx, msg in enumerate(self.chat_history, 1)))
        return reply, sources


class ChatbotApp:
    def __init__(self, master: tk.Tk):
        self.master = master
        self.master.title("OpenAI Responses-API Chatbot - https://github.com/namor5772/OpenAIAPITkinterPlay/blob/main/ChatBot.py")

        # Setting up directories and special file paths
        script_dir = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
        self.base_dir = Path(script_dir) / "system_prompts"  
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.state_path = Path(script_dir) / STATE_FILE
        print(f'The system prompts are in {self.base_dir}')
        print(f'The STATE FILE path is {self.state_path}')

        # Tracks which base filename (stem) is currently loaded in the editor
        self.current_name: str | None = None
        self.current_chat_name: str | None = None


        # --- System Prompt UI elements ----------------------------------------

        self.lbl_save = tk.Label(master, text="Save System Prompt as :")
        self.lbl_save.place(x=PADX, y=PADY+2) # small +3 vertical nudge to align with the Entry control
        self.var_filename = tk.StringVar()
        self.ent_name = tk.Entry(master, textvariable=self.var_filename)
        self.ent_name.place(x=PADX+136, y=PADY, width=255, height=26)
        self.ent_name.bind("<Return>", lambda e: self.var_filename.get().strip() and self.save_as_clicked())
        #self.ent_name.bind("<FocusOut>", lambda e: self.var_filename.get().strip() and self.save_as_clicked())

        self.lbl_load = tk.Label(master, text="Load System Prompt     :")
        self.lbl_load.place(x=PADX, y=PADY+2+35)

        self.var_choice = tk.StringVar()
        self.cbo_files = ttk.Combobox(master, textvariable=self.var_choice, state="readonly")
        self.cbo_files.place(x=PADX+136, y=PADY+35, width=255, height=26)
        self.cbo_files.bind("<Return>", self.load_selected)              # Enter loads
        self.cbo_files.bind("<<ComboboxSelected>>", self.load_selected)  # optional immediate load

        self.btn_delete = tk.Button(master, text="DELETE", command=self.delete_file)
        self.btn_delete.place(x=WINDOW_WIDTH_actual-177, y=PADY, width=70, height=26)

        self.btn_clear = tk.Button(master, text="CLEAR", command=self.clear_all_reset)
        self.btn_clear.place(x=WINDOW_WIDTH_actual-97, y=PADY, width=70, height=26)

        self.txt = ScrolledText(master, wrap=tk.WORD, undo=True, bg="lightgrey")
        self.txt.place(x=PADX, y=CHAT_DISPLAY_Y+35, width=WINDOW_W - 20, height=CHAT_DISPLAY_HEIGHT+34-35)

        # --- System Prompt UI elements -- END ---------------------------------


        # Keyboard convenience  
        self.master.bind_all("<Control-s>", self._accelerator_save)
        self.master.bind_all("<Control-S>", self._accelerator_save)

        # NEW: Ctrl+N → New (clear editor and reset state)
        self.master.bind_all("<Control-n>", self._accelerator_clear)
        self.master.bind_all("<Control-N>", self._accelerator_clear)

        # Populate combobox with existing .txt files (no extensions)
        self.refresh_combobox()

        # Try to restore last session (loads file, sets entry, selects/focuses combo)
        self.restore_state_or_focus_editor()

        # Intercept window close to persist state
        self.master.protocol("WM_DELETE_WINDOW", self.on_close)

        # sets up the chatbot models global array MODEL_OPTIONS[], among other things
        self.bot = ChatMemoryBot()
        self.last_sources: List[str] = []  # stores sources for the most recent bot message
        self.pending_images: List[Dict[str, str]] = []  # photos queued for the next user message
        self._thumb_cache: List[Any] = []  # keep references to PhotoImage thumbs
        self.labels = MODEL_OPTIONS
        self.initial_label = MODEL_OPTIONS[0]


        # --- Chat session UI elements ----------------------------------------

        self.lbl_model = tk.Label(master, text="Model :")
        self.lbl_model.place(x=10, y=PADY+1)
     
        self.model_var = tk.StringVar(master, value=self.initial_label)
        self.model_cmb = ttk.Combobox(master, state="readonly", values=self.labels, textvariable=self.model_var)
        self.model_cmb.place(x=MODEL_CMB_X, y=MODEL_CMB_Y, width=MODEL_CMB_WIDTH, height=MODEL_CMB_HEIGHT)
        self.model_cmb.bind("<<ComboboxSelected>>", lambda event: self.select_model())

        self.lbl_saveChat = tk.Label(master, text="Save Chat as :")
        self.lbl_saveChat.place(x=MODEL_CMB_X+MODEL_CMB_WIDTH+10, y=PADY+1)
        self.var_filenameChat = tk.StringVar()
        self.ent_nameChat = tk.Entry(master, textvariable=self.var_filenameChat)
        self.ent_nameChat.place(x=MODEL_CMB_X+MODEL_CMB_WIDTH+90, y=PADY, width=200, height=26)
        self.ent_nameChat.bind("<Return>", lambda e: self.var_filenameChat.get().strip() and self.saveChat_as_clicked())
        #self.ent_nameChat.bind("<FocusOut>", lambda e: self.var_filenameChat.get().strip() and self.saveChat_as_clicked())

        self.lbl_loadChat = tk.Label(master, text="Load Chat :")
        self.lbl_loadChat.place(x=MODEL_CMB_X+MODEL_CMB_WIDTH+213+85, y=PADY+1)

        self.var_choiceChat = tk.StringVar()
        self.cbo_filesChat = ttk.Combobox(master, textvariable=self.var_choiceChat, state="readonly")
        self.cbo_filesChat.place(x=MODEL_CMB_X+MODEL_CMB_WIDTH+365, y=PADY, width=200, height=26)
        self.cbo_filesChat.bind("<Return>", self.load_selectedChat)              # Enter loads
        self.cbo_filesChat.bind("<<ComboboxSelected>>", self.load_selectedChat)  # optional immediate load
        self.refresh_comboboxChat()

        self.btn_deleteChat = tk.Button(master, text="DELETE", command=self.delete_fileChat)
        self.btn_deleteChat.place(x=WINDOW_WIDTH-177, y=PADY, width=70, height=26)

        self.btn_newChat = tk.Button(master, text="NEW CHAT", command=self.new_chat)
        self.btn_newChat.place(x=WINDOW_WIDTH-97, y=PADY, width=70, height=26)

        self.chat_display = ScrolledText(master, wrap=tk.WORD, state='disabled', bg="white")
        self.chat_display.place(x=CHAT_DISPLAY_X, y=CHAT_DISPLAY_Y, width=CHAT_DISPLAY_WIDTH, height=CHAT_DISPLAY_HEIGHT)

        # Attachment bar (sits just above the input row)
        bar_width = SOURCES_BUTTON_X + SOURCES_BUTTON_WIDTH - ATTACH_BUTTON_X
        self.attachments_bar = tk.Frame(master, bg="#eef1f5", bd=0)
        self.attachments_bar.place(x=ATTACH_BUTTON_X, y=INPUT_Y-ATTACH_BAR_HEIGHT-6, width=bar_width, height=ATTACH_BAR_HEIGHT)
        self.attachments_holder = tk.Frame(self.attachments_bar, bg="#f4f4f4")
        self.attachments_holder.pack(side="left", fill="both", expand=True, padx=(6, 0))
        self.clear_attachments_btn = tk.Button(self.attachments_bar, text="Clear", command=self.clear_attachments, state="disabled", padx=6)
        self.clear_attachments_btn.pack(side="right", padx=(6, 6), pady=2)

        self.attach_button = tk.Button(master, text="Add photos", command=self.add_images)
        self.attach_button.place(x=ATTACH_BUTTON_X, y=INPUT_Y, width=ATTACH_BUTTON_WIDTH, height=ATTACH_BUTTON_HEIGHT)

        self.user_input = tk.Entry(master, bg="lightgray")
        self.user_input.place(x=INPUT_X, y=INPUT_Y, width=INPUT_WIDTH, height=INPUT_HEIGHT)
        self.user_input.bind("<Return>", self.send_message)

        self.send_button = tk.Button(master, text=SEND_BTN_LABEL, command=self.send_message)
        self.send_button.place(x=SEND_BUTTON_X, y=INPUT_Y, width=SEND_BUTTON_WIDTH, height=SEND_BUTTON_HEIGHT)

        self.src_button = tk.Button(master, text=SRC_BTN_LABEL, command=self.show_sources)
        self.src_button.place(x=SOURCES_BUTTON_X, y=SOURCES_BUTTON_Y, width=SOURCES_BUTTON_WIDTH, height=SOURCES_BUTTON_HEIGHT)

        # --- Chat session UI elements -- END ---------------------------------


        # Make all buttons keyboard-accessible
        for b in (
            self.btn_delete,
            self.btn_clear,
            self.btn_newChat,
            self.btn_deleteChat,
            self.src_button,
            self.attach_button,
            self.send_button,
            self.clear_attachments_btn,
        ):
            self._keyboardize_button(b)

        # ... existing end-of-__init__ code ...
        self.restore_chat_after_init()
        self._render_attachment_pills()



    # -----------------------
    # Persist/restore helpers
    # -----------------------
    def _serialize_current_chat(self) -> Dict[str, Any]:
        """
        Build the same payload your saveChat_as_clicked() writes,
        suitable for autosave or manual save.
        """
        model_in_use = self.model_cmb.get() or getattr(self.bot, "browse_model", "")
        browse_enabled = ENABLE_HOSTED_WEB_SEARCH
        system_prompt_name = self.current_name  # may be None
        system_prompt_text = self.txt.get("1.0", tk.END)
        chat_display_text = self.chat_display.get("1.0", tk.END)
        chat_history = list(self.bot.chat_history)

        return {
            "meta": {"version": 1},
            "saved_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
            "model": model_in_use,
            "browse_enabled": browse_enabled,
            "system_prompt_name": system_prompt_name,
            "system_prompt_text": system_prompt_text,
            "chat_display_plaintext": chat_display_text,
            "chat_history": chat_history,
        }

    def _apply_chat_payload(self, data: Dict[str, Any]) -> None:
        """
        Restore a chat session from a parsed payload dict (as saved by _serialize_current_chat()).
        Used by manual load and autosave restore.
        """
        # 1) Fields
        saved_model = data.get("model", "")
        saved_browse = data.get("browse_enabled", None)
        sp_name      = data.get("system_prompt_name")
        sp_text      = data.get("system_prompt_text", "")
        transcript   = data.get("chat_display_plaintext", "")
        hist         = data.get("chat_history", [])

        # 2) Model restore if available
        if saved_model and (saved_model in list(self.model_cmb["values"])):
            self.model_var.set(saved_model)
            self.select_model()  # keeps bot.* models in sync

        # 3) Browse toggle
        if saved_browse is not None:
            global ENABLE_HOSTED_WEB_SEARCH
            ENABLE_HOSTED_WEB_SEARCH = bool(saved_browse)

        # 4) System prompt editor + filename reflection (if present)
        self.txt.delete("1.0", tk.END)
        self.txt.insert(tk.END, sp_text or "")

        if sp_name:
            prompt_names = list(self.cbo_files["values"])
            if sp_name in prompt_names:
                self.var_choice.set(sp_name)
                self._select_combo_item(sp_name)
                self.var_filename.set(sp_name)
                self.current_name = sp_name
            else:
                self.var_choice.set("")
                self.cbo_files.set("")
                self.var_filename.set("")
                self.current_name = None

        # 5) Transcript
        self.chat_display.configure(state='normal')
        self.chat_display.delete("1.0", tk.END)
        self.chat_display.insert(tk.END, transcript or "")
        self.chat_display.configure(state='disabled')
        self.chat_display.see(tk.END)

        # 6) Structured history + bot system prompt
        if isinstance(hist, list) and all(isinstance(m, dict) for m in hist):
            self.bot.chat_history = hist
            if hist and isinstance(hist[0], dict) and hist[0].get("role") == "system":
                self.bot.str_system_prompt = hist[0].get("content", self.bot.str_system_prompt)
        else:
            self.bot.chat_history = [
                {"role": "system", "content": sp_text or self.bot.str_system_prompt}
            ]


    # -----------------------
    # Persist/restore helpers
    # -----------------------
    def _persist_state(self):
        """
        Save both the last system prompt filename (if any) and last chat name (if any).
        """
        data = {
            "last_file": self.current_name,
            "last_chat": self.current_chat_name,
        }
        try:
            self.state_path.write_text(json.dumps(data), encoding="utf-8")
        except Exception:
            pass  # non-fatal

    def _load_state(self) -> Dict[str, Optional[str]]:
        """
        Load state file robustly. Returns dict with keys "last_file" and "last_chat".
        Backward compatible with older state that only had last_file.
        """
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return {
                    "last_file": data.get("last_file"),
                    "last_chat": data.get("last_chat"),
                }
        except Exception:
            pass
        return {"last_file": None, "last_chat": None}


    # -----------------------
    # Chat session helpers
    # -----------------------
    def list_chat_basenames(self) -> list[str]:
        """
        Return a sorted list of saved chat session names (without extension).
        Looks for files named *.chat.json in base_dir.
        """
        names: list[str] = []
        for p in self.base_dir.glob("*.chat.json"):
            # strip the trailing ".chat.json" from the filename
            fname = p.name
            if fname.endswith(".chat.json"):
                names.append(fname[:-10])  # remove .chat.json (10 chars)
        names.sort()
        return names


    def refresh_comboboxChat(self):
        """Populate chat session combobox with the names of saved sessions."""
        names = self.list_chat_basenames()
        self.cbo_filesChat["values"] = names


    def _select_combo_itemChat(self, name: str):
        """Select 'name' in the chat combobox and focus it, if present."""
        values = list(self.cbo_filesChat["values"])
        if name in values:
            self.cbo_filesChat.current(values.index(name))
        self.cbo_filesChat.focus_set()


    def new_chat(self) -> None:
        """
        Save the current chat (named -> named file, unnamed -> autosave),
        then clear name field and start a fresh conversation using the editor's system prompt.
        """
        # --- 0) Persist current session first (silent) --------------------------
        try:
            if self.current_chat_name:
                # Save to the named file
                self._save_named_chat(self.current_chat_name)
            else:
                # No name: write autosave
                self._write_autosave()
        except Exception as e:
            # Non-fatal: continue to start the new chat regardless
            print(f"[NEW CHAT] Pre-save failed: {e}")

        # --- 1) Clear the chat *name* UI so we don't carry it forward -----------
        self.current_chat_name = None
        self.var_filenameChat.set("")   # Entry under SAVE AS (chat)
        self.var_choiceChat.set("")     # Backing var for chat combobox
        self.cbo_filesChat.set("")      # Clear visible selection
        # If you want the list to reflect any new named save that might have been created, refresh:
        self.refresh_comboboxChat()

        # --- 2) Decide which system prompt to use -------------------------------
        new_system_prompt = self.txt.get("1.0", tk.END).strip()
        if not new_system_prompt:
            new_system_prompt = self.bot.str_system_prompt  # keep existing if editor is empty

        # --- 3) Reset the bot to a fresh conversation ---------------------------
        self.bot.reset(system_prompt=new_system_prompt)

        # --- 4) Clear the visible chat transcript -------------------------------
        self.chat_display.configure(state='normal')
        self.chat_display.delete("1.0", tk.END)
        self.chat_display.configure(state='disabled')

        # --- 5) Clear last sources and any pending input ------------------------
        self.last_sources = []
        self.user_input.delete(0, tk.END)
        self.clear_attachments()

        # --- 6) Provide the usual visual cue -----------------------------------
        self.chat_display.configure(state='normal')
        self.chat_display.insert(tk.END, "- New chat started -\n\n")
        self.chat_display.configure(state='disabled')
        self.chat_display.see(tk.END)

        # Optional: move typing focus to the input box for immediate chatting
        #self.user_input.focus_set()
        self.ent_nameChat.focus_set()   # instead of self.user_input.focus_set()

        # --- 7) Persist lightweight state ---------------------------------------
        self._persist_state()

        print("[UI] New chat started. System prompt in use:")
        print(new_system_prompt)


    # -----------------------
    # Helpers
    # -----------------------
    def _keyboardize_button(self, btn: tk.Widget) -> None:
        """
        Make a button focusable via Tab/Shift-Tab and activatable via Enter/Space.
        Works for tk.Button and ttk.Button.
        """
        # Ensure it can receive keyboard focus
        try:
            btn.configure(takefocus=True) # type: ignore
        except tk.TclError:
            pass  # some themed widgets may not expose takefocus; ok to skip

        # Bind keys to invoke() when the button has focus
        def _invoke(_event=None, _b=btn):
            try:
                _b.invoke() # type: ignore
            except Exception:
                # If a widget masquerades as a button but lacks .invoke()
                pass
            return "break"  # prevent the key event from propagating further

        btn.bind("<Return>", _invoke)     # main Enter
        btn.bind("<KP_Enter>", _invoke)   # numeric keypad Enter
        btn.bind("<space>", _invoke)      # Spacebar


    # -----------------------
    # Attachment helpers
    # -----------------------
    @staticmethod
    def _image_to_data_url(path: str) -> str:
        mime, _ = mimetypes.guess_type(path)
        if not mime:
            mime = "image/png"
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        return f"data:{mime};base64,{b64}"

    def _build_thumbnail(self, path: str, size: int = 36) -> Optional[Any]:
        """
        Create a small thumbnail image for display beside the filename.
        Uses Pillow if available; otherwise returns a flat placeholder square.
        """
        try:
            if Image and ImageTk:
                img = Image.open(path)
                img.thumbnail((size, size))
                return ImageTk.PhotoImage(img)
        except Exception:
            pass
        try:
            ph = tk.PhotoImage(width=size, height=size)
            ph.put("#d8dce3", to=(0, 0, size, size))
            ph.put("#c2c7cf", to=(1, 1, size-1, size-1))
            return ph
        except Exception:
            return None


    def _render_attachment_pills(self) -> None:
        """Refresh the inline chips that show pending photos."""
        for child in self.attachments_holder.winfo_children():
            child.destroy()
        self._thumb_cache.clear()

        if not self.pending_images:
            tk.Label(self.attachments_holder, text="No photos attached", anchor="w", fg="#555", bg="#f4f4f4", padx=4).pack(side="left")
            self.clear_attachments_btn.configure(state="disabled")
            return

        self.clear_attachments_btn.configure(state="normal")
        for idx, item in enumerate(self.pending_images):
            pill = tk.Frame(self.attachments_holder, bg="#e6eaef", bd=1, relief="solid")
            thumb = item.get("thumb")
            if thumb is not None:
                lbl_thumb = tk.Label(pill, image=thumb, bg="#e6eaef")
                lbl_thumb.image = thumb  # type: ignore # prevent GC
                lbl_thumb.pack(side="left", padx=(4, 2), pady=1)
                self._thumb_cache.append(thumb)
            tk.Label(pill, text=item.get("filename", "photo"), bg="#e6eaef").pack(side="left", padx=(2, 4))
            tk.Button(pill, text="✕", command=lambda i=idx: self.remove_attachment(i), padx=4, pady=0, bg="#dbe0e8", relief="flat").pack(side="right", padx=(0, 2), pady=1)
            pill.pack(side="left", padx=4, pady=2)


    def add_images(self) -> None:
        """Open a file picker and stage one or more images for the next message."""
        paths = filedialog.askopenfilenames(
            title="Select photos",
            filetypes=[("Images", "*.png;*.jpg;*.jpeg;*.webp;*.gif"), ("All files", "*.*")],
        )
        if not paths:
            return

        added = 0
        for p in paths:
            try:
                data_url = self._image_to_data_url(p)
            except Exception as e:
                messagebox.showerror("Image error", f"Could not read {p}:\n{e}")
                continue
            name = os.path.basename(p)
            thumb = self._build_thumbnail(p)
            self.pending_images.append({"filename": name, "data_url": data_url, "thumb": thumb}) # type: ignore
            added += 1

        if added:
            self._render_attachment_pills()


    def remove_attachment(self, index: int) -> None:
        if 0 <= index < len(self.pending_images):
            del self.pending_images[index]
        self._render_attachment_pills()


    def clear_attachments(self) -> None:
        self.pending_images.clear()
        self._render_attachment_pills()


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


    def delete_file(self):
        """Delete the current file, clear the text area, and update combobox list."""
        if not self.current_name:
            messagebox.showwarning("No file", "No file is currently open to delete.")
            return

        # Confirm deletion
        file_to_delete = self.base_dir / f"{self.current_name}.txt"
        if not file_to_delete.exists():
            messagebox.showerror("File not found", f"Could not find {file_to_delete.name} to delete.")
            return

        # Ask user to confirm
        confirm = messagebox.askyesno(
            "Confirm Deletion",
            f"Are you sure you want to delete the file:\n{file_to_delete.name}"
        )
        if not confirm:
            return

        # Delete the file
        try:
            file_to_delete.unlink()  # Delete the file
            messagebox.showinfo("File Deleted", f"File {file_to_delete.name} has been deleted.")
        except Exception as e:
            messagebox.showerror("Delete Failed", f"Failed to delete the file: {e}")
            return

        # Update the Combobox (remove the deleted file from the list)
        self.refresh_combobox()

        self.txt.delete("1.0", tk.END)   # empty editor
        self.var_filename.set("")        # clear filename Entry
        self.var_choice.set("")          # clear combobox variable text
        self.cbo_files.set("")           # ensure UI shows no selection
        self.current_name = None         # forget which file was 'open'
        self.txt.focus_set()             # caret back to editor


    def delete_fileChat(self):
        """
        Delete the selected (or current) saved chat session (*.chat.json) from base_dir.
        Refreshes the chat combobox, clears UI/state if the deleted session was loaded,
        and attempts to select a remaining session if available.
        """
        # 1) Determine which chat session to delete
        name = (self.var_choiceChat.get() or (self.current_chat_name or "")).strip()
        if not name:
            messagebox.showwarning("No chat selected", "Select a chat session in the list first.")
            return

        target = self.base_dir / f"{name}.chat.json"
        if not target.exists():
            messagebox.showerror("Not found", f"Chat session file not found:\n{target}")
            return

        # 2) Confirm deletion
        if not messagebox.askyesno(
            "Confirm Deletion",
            f"Are you sure you want to delete the chat session:\n{target.name}"
        ):
            return

        # 3) Delete the file
        try:
            target.unlink()
        except Exception as e:
            messagebox.showerror("Delete Failed", f"Failed to delete the chat session:\n{e}")
            return

        # 4) Refresh the chat session combobox
        self.refresh_comboboxChat()

        # 5) If we just deleted the currently loaded chat, clear UI/state
        if self.current_chat_name == name or self.var_choiceChat.get().strip() == name:
            # Clear combobox/entry state for chats
            self.current_chat_name = None
            self.var_filenameChat.set("")
            self.var_choiceChat.set("")
            self.cbo_filesChat.set("")

            # Clear transcript
            self.chat_display.configure(state='normal')
            self.chat_display.delete("1.0", tk.END)
            self.chat_display.configure(state='disabled')

            # Clear last sources and pending input
            self.last_sources = []
            self.user_input.delete(0, tk.END)

            # Reset the bot to a single system message using current editor text
            current_sp = self.txt.get("1.0", tk.END).strip() or self.bot.str_system_prompt
            self.bot.reset(system_prompt=current_sp)

        # 6) Try to select another existing chat (if any remain)
        remaining = list(self.cbo_filesChat["values"])
        if remaining:
            # pick the last one alphabetically (or any policy you prefer)
            next_name = remaining[-1]
            self.var_choiceChat.set(next_name)
            self._select_combo_itemChat(next_name)
        else:
            # No remaining chats; just focus the chat list to signal completion
            self.cbo_filesChat.focus_set()

        self._persist_state()
        messagebox.showinfo("Deleted", f"Deleted chat session:\n{target}")


    def _accelerator_save(self, event: Optional[tk.Event] = None) -> str:
        self.save_as_clicked()
        return "break"


    def _accelerator_clear(self, event: Optional[tk.Event] = None) -> str:
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


    def saveChat_as_clicked(self):
        """
        Save the current chat session to a JSON file in the same folder as system prompts.
        File name is taken from ent_nameChat (without extension).
        Saved fields:
          - model in use
          - whether hosted web search is enabled
          - system prompt filename (if loaded) and text
          - visible chat transcript (plaintext)
          - structured chat_history array from the bot
        """
        # 1) Validate and sanitize the target name
        raw = self.var_filenameChat.get()
        name = self._sanitize_filename(raw)
        if not name:
            messagebox.showwarning("Missing name", "Please type a chat session name.")
            self.ent_nameChat.focus_set()
            return

        # 2) Build the target path: <base_dir>/<name>.chat.json
        target = (self.base_dir / f"{name}.chat.json")

        # 3) Collect the data we want to persist
        # Current model (both app & bot kept in sync by select_model)
        model_in_use = self.model_cmb.get() or getattr(self.bot, "browse_model", "")
        # Whether hosted web search is enabled
        browse_enabled = ENABLE_HOSTED_WEB_SEARCH
        # System prompt info (filename + text)
        system_prompt_name = self.current_name  # may be None if not saved/loaded
        system_prompt_text = self.txt.get("1.0", tk.END)

        # Visible chat as plaintext
        chat_display_text = self.chat_display.get("1.0", tk.END)

        # Structured chat history from bot
        chat_history = list(self.bot.chat_history)

        payload = {
            "meta": {"version": 1},
            "saved_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
            "model": model_in_use,
            "browse_enabled": browse_enabled,
            "system_prompt_name": system_prompt_name,
            "system_prompt_text": system_prompt_text,
            "chat_display_plaintext": chat_display_text,
            "chat_history": chat_history,
        }

        # 4) Write file (with overwrite confirmation)
        try:
            if target.exists():
                if not messagebox.askyesno(
                    "Overwrite?",
                    f"“{target.name}” already exists.\nDo you want to overwrite it?"
                ):
                    return

            target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

        except Exception as e:
            messagebox.showerror("Save failed", f"Could not save chat session:\n{e}")
            return

        # 5) Update the chat combobox if new, then select & focus it
        current = list(self.cbo_filesChat["values"])
        if name not in current:
            current.append(name)
            current.sort()
            self.cbo_filesChat["values"] = current

        self.var_choiceChat.set(name)
        self._select_combo_itemChat(name)
        self.var_filenameChat.set(name)

        self.current_chat_name = name
        self._persist_state()
        messagebox.showinfo("Saved", f"Chat session saved to:\n{target}")


    def load_selected(self, event: Optional[tk.Event] = None) -> None:
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


    def load_selectedChat(self, event: Optional[tk.Event] = None) -> None:
        """
        Pre-save the current chat (if named -> named file; else autosave as a safety net),
        then load the newly selected chat from the combobox.
        """
        # --- A) Determine the next chat to load --------------------------------
        name = self.var_choiceChat.get().strip()
        if not name:
            return
        path = self.base_dir / f"{name}.chat.json"
        if not path.exists():
            messagebox.showerror("Not found", f"Chat session not found:\n{path}")
            return

        # --- B) PRE-SAVE the current session before switching -------------------
        try:
            if self.current_chat_name:
                # Save the current session under its existing name
                self._save_named_chat(self.current_chat_name)
            else:
                # Safety net (remove this line if you *don’t* want autosave here)
                self._write_autosave()
        except Exception as e:
            # Non-fatal – still proceed to load the requested chat
            print(f"[Load] Pre-save failed: {e}")

        # If the user re-selected the same chat, we can just reload it; that’s OK.
        # If you prefer to short-circuit instead:
        # if self.current_chat_name and name == self.current_chat_name:
        #     self.user_input.focus_set()
        #     return

        # --- C) Load the requested chat -----------------------------------------
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            messagebox.showerror("Load failed", f"Invalid chat session file:\n{e}")
            return

        self._apply_chat_payload(data)

        # --- D) Mirror in UI and state ------------------------------------------
        self.current_chat_name = name
        self.var_filenameChat.set(name)
        self.var_choiceChat.set(name)
        self._select_combo_itemChat(name)
        self.refresh_comboboxChat()  # in case files changed due to pre-save

        # Persist the "last_chat" pointer so we restore this on next launch
        self._persist_state()

        # --- E) UX nicety: typing focus into the input field --------------------
        self.user_input.focus_set()

        messagebox.showinfo("Loaded", f"Chat session loaded:\n{path}")


    def _save_named_chat(self, name: str) -> Path:
        """
        Silently save the current session to <base_dir>/<name>.chat.json.
        No prompts or message boxes; used by on_close autosave-to-named.
        """
        payload = self._serialize_current_chat()
        target = (self.base_dir / f"{name}.chat.json")
        # Overwrite without asking – this is an autosave-on-exit of a named chat
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return target


    def _write_autosave(self) -> Path:
        """
        Write the current session to _autosave.chat.json silently.
        """
        payload = self._serialize_current_chat()
        autosave_path = self.base_dir / CHAT_AUTOSAVE_FILE
        autosave_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return autosave_path


    def restore_state_or_focus_editor(self):
        """
        On startup, try to restore last *system prompt* file; else show empty editor.
        Always give focus to the text area for immediate typing.
        """
        state = self._load_state()
        self.refresh_combobox()
        last_file = state.get("last_file")
        if last_file and (self.base_dir / f"{last_file}.txt").exists():
            # Select it in combo and load its content
            self.var_choice.set(last_file)
            self.load_selected()
        # Always focus the text area on startup
        self.txt.focus_set()


    def restore_chat_after_init(self):
        """
        After models/bot/UI are ready, try to restore the last chat if present; else autosave.
        """
        self.refresh_comboboxChat()

        state = self._load_state()
        last_chat = state.get("last_chat") if isinstance(state, dict) else None

        # 1) Try last named chat
        if last_chat:
            path = self.base_dir / f"{last_chat}.chat.json"
            if path.exists():
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                    self._apply_chat_payload(data)
                    self.current_chat_name = last_chat
                    self.var_filenameChat.set(last_chat)
                    self.var_choiceChat.set(last_chat)
                    self._select_combo_itemChat(last_chat)
                    self.user_input.focus_set()  # NEW: focus input
                    return
                except Exception as e:
                    print(f"[Restore] Failed to load last_chat: {e}")

        # 2) Fall back to autosave
        autosave_path = self.base_dir / CHAT_AUTOSAVE_FILE
        if autosave_path.exists():
            try:
                data = json.loads(autosave_path.read_text(encoding="utf-8"))
                self._apply_chat_payload(data)
                # Do not set current_chat_name here (autosave is unnamed by design)
                self.var_filenameChat.set("")
                self.var_choiceChat.set("")
                self.cbo_filesChat.set("")
                print("[Restore] Restored from autosave.")
                self.user_input.focus_set()  # NEW: focus input
                return
            except Exception as e:
                print(f"[Restore] Failed to load autosave: {e}")

        print("[Restore] No last chat or autosave found.")
        # If nothing to restore, still put cursor where you want it:
        self.user_input.focus_set()  # NEW: focus input when starting fresh


    def on_close(self):
        """
        If the current chat has a name, persist it to <name>.chat.json on exit.
        Otherwise, fall back to _autosave.chat.json.
        Also persist 'last_file' and 'last_chat' state, then exit.
        """
        try:
            if self.current_chat_name:
                # Named chat: save to its file
                try:
                    self._save_named_chat(self.current_chat_name)
                except Exception as e:
                    print(f"[Exit Save] Failed to save named chat '{self.current_chat_name}': {e}")
                    # As a safety net, also write an autosave so nothing is lost
                    try:
                        autosave_path = self.base_dir / CHAT_AUTOSAVE_FILE
                        autosave_path.write_text(
                            json.dumps(self._serialize_current_chat(), ensure_ascii=False, indent=2),
                            encoding="utf-8"
                        )
                    except Exception as e2:
                        print(f"[Autosave Fallback] Failed: {e2}")
            else:
                # Unnamed chat: autosave
                try:
                    autosave_path = self.base_dir / CHAT_AUTOSAVE_FILE
                    autosave_path.write_text(
                        json.dumps(self._serialize_current_chat(), ensure_ascii=False, indent=2),
                        encoding="utf-8"
                    )
                except Exception as e:
                    print(f"[Autosave] Failed: {e}")
        finally:
            # Persist lightweight state no matter what
            self._persist_state()
            self.master.destroy()


    def select_model(self):
        """
        Update the bot's model based on the selected value in the combobox.
        """
        chosen = self.model_cmb.get()
        # Update both the app and the bot so they stay in sync
        self.default_model = chosen
        self.browse_model = chosen
        self.bot.default_model = chosen
        self.bot.browse_model = chosen # For simplicity, use the same model for browsing
        print(f"Model changed to: {chosen}")

    def _format_user_display(self, text: str, attachments: List[Dict[str, str]]) -> str:
        """Compose the transcript text shown for a user message."""
        if attachments:
            names = ", ".join(img.get("filename", "photo") for img in attachments)
            if text:
                return f"{text}\n[Photos: {names}]"
            return f"[Photos: {names}]"
        return text

    def send_message(self, _: Optional[Any] = None) -> None:
        user_text = self.user_input.get().strip()
        attachments = list(self.pending_images)
        if not user_text and not attachments:
            return

        self.display_message("You", self._format_user_display(user_text, attachments))
        self.user_input.delete(0, tk.END)
        self.clear_attachments()
        threading.Thread(target=self.get_bot_response, args=(user_text, attachments), daemon=True).start()


    def get_bot_response(self, user_text: str, attachments: List[Dict[str, str]]):
        try:
            reply, sources = self.bot.ask(user_text, attachments)
            self.last_sources = sources or []
        except Exception as e:
            reply = f"[Error] {type(e).__name__}: {e}"
            self.last_sources = []
        self.display_message("Bot", reply)


    def display_message(self, sender: str, message: str) -> None:
        self.chat_display.configure(state='normal')
        self.chat_display.insert(tk.END, f"{sender}: {message}\n\n")
        self.chat_display.configure(state='disabled')
        self.chat_display.see(tk.END)


    def show_sources(self) -> None:
        self.chat_display.configure(state='normal')
        if not self.last_sources:
            self.chat_display.insert(tk.END, "Sources: (none detected)\n\n")
        else:
            self.chat_display.insert(tk.END, "Sources:\n")
            for i, src in enumerate(self.last_sources, 1):
                self.chat_display.insert(tk.END, f"  {i}. {src}\n")
            self.chat_display.insert(tk.END, "\n")
        self.chat_display.configure(state='disabled')
        self.chat_display.see(tk.END)


if __name__ == "__main__":
    root = tk.Tk()

    root.geometry(f"{WINDOW_WIDTH_actual}x{WINDOW_HEIGHT}+0+0")
    root.resizable(False, False)
    app = ChatbotApp(root)
    root.mainloop()
