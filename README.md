# ChatBot.py — A local Tkinter client for the OpenAI Responses API

A desktop chat client written in Python/Tkinter that lets you:

- Author and save **system prompts** as plain `.txt` files
- Run **chat sessions** against OpenAI models (with optional hosted web search tools)
- **Save/Load/Delete** entire chat sessions as `.chat.json`
- **Autosave** on exit and **auto-restore** on launch
- Pick a **model** from your OpenAI account dynamically
- Extract and display **sources/URLs** returned by the model
- Drive everything with **keyboard-first** workflows

The application is single-file (`ChatBot.py`) and stores all user data under a `system_prompts` folder. Per-user UI state is stored in a hidden file next to the script.

---

## Quick start

```bash
# 1) Create a virtual environment (recommended)
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

# 2) Install dependencies
pip install --upgrade openai tiktoken

# 3) Set your OpenAI API key for this shell
# Windows (PowerShell)
setx OPENAI_API_KEY "sk-your-key"
$env:OPENAI_API_KEY = "sk-your-key"
# macOS/Linux
export OPENAI_API_KEY="sk-your-key"

# 4) Run the app
python ChatBot.py
```

> **Note (Linux only)**: Install Tkinter if missing, e.g. `sudo apt-get install python3-tk`.

---

## Table of contents

- [Screens & workflow](#screens--workflow)
- [Key features](#key-features)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the app](#running-the-app)
- [Data locations & file formats](#data-locations--file-formats)
- [Model selection & browsing](#model-selection--browsing)
- [Trimming & token management](#trimming--token-management)
- [Threading model](#threading-model)
- [Keyboard shortcuts & accessibility](#keyboard-shortcuts--accessibility)
- [Troubleshooting](#troubleshooting)
- [Project structure & extensibility](#project-structure--extensibility)
- [Security notes](#security-notes)
- [License](#license)

---

## Screens & workflow

The UI is split into two vertical areas:

- **Left (Chat)**  
  Model picker → **NEW CHAT** / Chat Save/Load/Delete → chat transcript (ScrolledText) → single-line input and **Show sources** button.

- **Right (System prompt editor)**  
  System-prompt Save/Load controls and a ScrolledText editor for authoring your system message.

Widget locations and sizes are controlled by layout constants near the top of the file.

---

## Key features

### System prompt management
- Write a prompt in the right-hand editor and **Save as** to `system_prompts/<name>.txt`.
- **Load** from the combobox; the editor updates and the filename reflects the selection.

### Chat sessions
- **NEW CHAT** first **pre-saves** the current session (named → named file; unnamed → `_autosave.chat.json`), clears the chat **name** field, then resets to the editor’s system prompt.
- **Save as** (chat) persists the entire session (model, prompt text, transcript, structured `chat_history`) to `system_prompts/<name>.chat.json`.
- **Load** (chat) restores all of the above, including the bot’s `chat_history`.

### Autosave & auto-restore
- On exit: named chats save to their own file; unnamed chats go to `_autosave.chat.json`.
- On launch: tries **last named chat**, else restores from `_autosave.chat.json`. For prompts, the app restores the **last-file** if available.

### Model discovery
- On startup, `client.models.list()` populates a Model combobox after filtering out non-chat models (embeddings, audio, search, realtime, preview, transcribe, tts, and `gpt-image-1`).

### Optional hosted web search
- `ENABLE_HOSTED_WEB_SEARCH = True` sends a tool spec `[{ "type": "web_search" }]`. If the model rejects tools, the app **retries without tools** automatically.

### Citations (sources)
- The app walks the structured response object and the assistant’s text for URLs and lists them via **Show sources**.

### Token trimming
- If a conversation exceeds `max_tokens` (default **20,000**), older messages are summarized (using the **default** model) into a single “Summary of earlier conversation” message.

---

## Installation

**Requirements**

- Python 3.10+
- OpenAI API key
- Packages: `openai` (v1+), `tiktoken`
- Tkinter (bundled on Windows/macOS Python; install separately on some Linux distros)

See the **Quick start** above for commands.

---

## Configuration

### OpenAI credentials

Set `OPENAI_API_KEY` in your environment. The OpenAI Python SDK will pick it up automatically.

### Hosted web search (optional)

At the top of the file:

```python
ENABLE_HOSTED_WEB_SEARCH = True
```

Set to `False` if you prefer pure LLM responses or don’t have access to the hosted tool. The code already retries without tools when necessary.

---

## Running the app

From the folder containing `ChatBot.py`:

```bash
python ChatBot.py
```

The app creates (if missing) a `system_prompts/` folder under your **current working directory** and stores a hidden state file `.textpad_state.json` next to `ChatBot.py`.

> **Alternative data location**: If you prefer the data folder relative to the script (not the working directory), replace:
> ```python
> self.base_dir = (Path.cwd() / "system_prompts").resolve()
> ```
> with:
> ```python
> self.base_dir = (Path(__file__).resolve().parent / "system_prompts").resolve()
> ```

---

## Data locations & file formats

### Folder layout

```
system_prompts/
  ├── <prompt-name>.txt            # system prompts (plain text)
  ├── <chat-name>.chat.json        # saved chats (JSON)
  └── _autosave.chat.json          # unnamed chat autosave
```

### State file

- `.textpad_state.json` (next to `ChatBot.py`):
  ```json
  {
    "last_file": "<prompt-name or null>",
    "last_chat": "<chat-name or null>"
  }
  ```

### Saved chat JSON structure

```json
{
  "meta": { "version": 1 },
  "saved_at": "2025-08-22T16:22:07",
  "model": "gpt-5-something",
  "browse_enabled": true,
  "system_prompt_name": "MyPrompt",
  "system_prompt_text": "...the actual prompt text...",
  "chat_display_plaintext": "You: ...\n\nBot: ...\n\n",
  "chat_history": [
    {"role": "system", "content": "..."},
    {"role": "user", "content": "Hi"},
    {"role": "assistant", "content": "Hello"}
  ]
}
```

---

## Model selection & browsing

- The **Model** combobox is populated from `client.models.list()` with chat-capable models only.
- Changing the combobox updates:
  - `bot.default_model` (used for non-tool calls like summaries)
  - `bot.browse_model` (used when `ENABLE_HOSTED_WEB_SEARCH` is true)
- If the chosen model rejects tools, the app logs a warning and **retries without tools** automatically.

---

## Trimming & token management

- `ChatMemoryBot.max_tokens` defaults to **20,000** tokens.
- Token counting uses `tiktoken` with a model-aware encoder. Fallbacks:
  - `o200k_base` for long-context names (`gpt-5`, `4.1`, `4o`, `o4`, `o3`, `200k`)
  - `cl100k_base` otherwise
- When the limit is exceeded, older messages (except the last ~10) are summarized by the **default** model into a single assistant message.

---

## Threading model

- API calls run in a **daemon thread** so the UI remains responsive.
- The background worker writes back to the UI when complete via `display_message(...)`.
- If you encounter cross-thread UI quirks, route updates with `self.master.after(0, ...)` to ensure execution on the main thread.

---

## Keyboard shortcuts & accessibility

- **Global**
  - `Ctrl+S` → Save (system prompt editor)
  - `Ctrl+N` → Clear the editor + reset filename/combobox

- **Comboboxes**
  - **System prompt**: **Enter** loads the selected file.
  - **Chat sessions**: **Enter** loads the selected chat.

- **Buttons**
  - All primary buttons are **Tab-focusable** and activatable with **Enter**, **KP_Enter**, or **Space**:
    - DELETE (prompt)
    - CLEAR (prompt)
    - NEW CHAT
    - DELETE (chat)
    - Show sources

- **Entries**
  - In **Save as** entries (prompt and chat), **Enter** triggers save.
  - On **focus-out**, a non-empty name also saves automatically.

---

## Troubleshooting

- **No models in dropdown / API errors**
  - Ensure `OPENAI_API_KEY` is set and valid.
  - Update SDK: `pip install --upgrade openai`.
  - Check network/proxy settings.

- **“Tool/model mismatch detected”**
  - Indicates the model doesn’t accept tools; the app already **retries without tools**.

- **Autosave didn’t restore**
  - Confirm `_autosave.chat.json` exists under `system_prompts/`.
  - Check console for JSON parse errors (e.g., after manual edits).

- **Cannot write files**
  - Ensure the current working directory is writable, or switch to the “script’s folder” base path.

---

## Project structure & extensibility

Two core classes keep responsibilities clear:

- `ChatMemoryBot`
  - Wraps OpenAI client
  - Tracks `chat_history`
  - Counts tokens & summarizes overflow
  - Builds request payloads (with/without tools)
  - Extracts sources/URLs from responses

- `ChatbotApp` (Tkinter)
  - UI layout & events
  - System-prompt persistence (`.txt`)
  - Chat session persistence (`.chat.json`)
  - Autosave/restore & last-used state
  - Keyboard accessibility
  - Threading for API calls

**Extension ideas**

- Add a Browse toggle checkbox bound to `ENABLE_HOSTED_WEB_SEARCH`.
- Export transcript to Markdown/HTML or PDF.
- Add sampling temperature and max-output-token controls.
- Route all UI updates through `after()` for strict Tk thread safety.

---

## Security notes

- Saved chats include your full transcript and system prompt. Avoid storing secrets in plain text.
- Consider OS-level encrypted folders or adding an encryption layer if you need to keep sensitive data.
- The state file only stores the last-used names, not contents, but it is still user data.

---

## License

You may license the project however you wish (MIT is common for personal tools). Example:

```
MIT License © 2025 Your Name
```
