# OpenAIAPITkinterPlay

This repo contains two Tkinter desktop utilities:

- `ChatBot.py`: keyboard-friendly OpenAI Responses API client with prompt/session management and optional browsing.
- `InsetNIP.py`: paste-one-record JSON-to-SQLite inserter for a `foods.db` nutrition database.

Most other files are supporting assets (icons, saved prompts/chats, helper scripts). The focus is on these two apps.

---

## Repository layout

- `ChatBot.py`: main chat client.
- `InsetNIP.py`: nutrition inserter GUI (filename kept as-is even though it reads as "Insert NIP").
- `system_prompts/`: saved prompt `.txt` files and chat session `.chat.json` files.
- `docs/`: screenshots and auxiliary docs for ChatBot (quickstart, shortcuts, architecture).
- `*.ico` / `*.png`: window icons and artwork.
- `.textpad_state*.json`: remembers the last-used prompt/chat for ChatBot.

---

## Environment setup (shared)

1. Install Python 3.10+ (Tkinter ships with python.org installers for Windows/macOS; Linux may need `python3-tk`).
2. Create a virtual environment:
   ```bash
   python -m venv .venv
   # Windows
   .venv\Scripts\activate
   # macOS/Linux
   source .venv/bin/activate
   ```
3. Install packages for ChatBot:
   ```bash
   pip install --upgrade pip
   pip install openai tiktoken
   # Optional (nicer thumbnails for attached photos):
   pip install pillow
   ```
4. Set your OpenAI API key for ChatBot:
   - PowerShell: `setx OPENAI_API_KEY "sk-..."` (restart shell afterwards)
   - macOS/Linux shell: `export OPENAI_API_KEY="sk-..."`

`InsetNIP.py` uses only the Python standard library (tkinter, sqlite3, json, pathlib) and needs no extra packages.

---

## ChatBot.py - OpenAI Responses desktop client

A single-window Tkinter app for multi-turn chatting with the OpenAI Responses API. It stays responsive, keeps your prompts organized, and autosaves your work.

### Core capabilities

- Model picker that filters to chat-capable models on your account.
- Side-by-side UI: chat history on the left, system-prompt editor on the right.
- Prompt manager: save/load/delete prompt files (`system_prompts/*.txt`).
- Session manager: save/load/delete named chats (`system_prompts/*.chat.json`) plus automatic `_autosave.chat.json` on exit.
- Autosave of the last-opened prompt/chat location in `.textpad_state.json`.
- Image attachments: add one or more photos to a question; they are sent as `input_image` parts alongside your text.
- Optional hosted `web_search` tool support with automatic retry if the selected model does not allow tools.
- Token counting with `tiktoken` and summarization of older turns when history grows large.
- Keyboard-friendly controls (Tab/Shift+Tab navigation, Enter/Space on buttons, shortcuts like Ctrl+S for saving prompts).

### Running ChatBot

From the repository root (after activating your venv and setting `OPENAI_API_KEY`):

```bash
python ChatBot.py
```

The app creates `system_prompts/` next to the script if it does not exist, then restores your last prompt/chat or the autosave. The window opens at a fixed size with chat on the left and the prompt editor on the right.

### Using ChatBot

- **System prompts**: edit in the right pane, then "Save System Prompt as" to create `system_prompts/<name>.txt`. "Load" brings one back; "Delete" removes the file after confirmation.
- **Chats**: "NEW CHAT" clears history but keeps the current prompt. "Save Chat as" creates `system_prompts/<name>.chat.json` containing the transcript and metadata. "Load" switches chats (the current one is autosaved first). "Delete" removes the selected chat file after confirmation.
- **Photos/attachments**: click **Add photos** above the input field to pick images (`png`, `jpg/jpeg`, `webp`, `gif`). Thumbnails appear in the attachment bar; use **Clear** or the per-photo remove button to drop them. Attached images are sent with your text in the next message.
- **Input/layout details**: the input row runs left-to-right with **Add photos**, a widened multi-line text box, and two stacked action buttons on the right. **Insert NIP** sits above **Show sources**; the text box expands vertically so its bottom aligns with the system-prompt editor for a clean baseline.
- **Sources**: a **Show sources** button appends URLs found in the response object or assistant text (stacked under **Insert NIP**).
- **Autosave and state**: the last prompt/chat name is stored in `.textpad_state.json`. Unnamed chats are written to `_autosave.chat.json` on exit and restored on next launch.

### Configuration notes

- The OpenAI SDK reads `OPENAI_API_KEY` from your environment.
- Browsing is controlled in code via `ENABLE_HOSTED_WEB_SEARCH` near the top of `ChatBot.py`. If disabled, requests are sent without the hosted `web_search` tool.

### Extra references

Older-but-useful docs live under `docs/`:

- `docs/QUICKSTART.md`: short setup/run guide.
- `docs/KEYBOARD_SHORTCUTS.md`: full shortcut list.
- `docs/ARCHITECTURE.md`: details on `ChatMemoryBot` (API/summarization) and `ChatbotApp` (UI layer).
- `docs/screenshot.png`: UI preview.

---

## InsetNIP.py - JSON to SQLite inserter

A small Tkinter helper for inserting a single food record into an existing `foods.db` SQLite database. You paste one JSON object; the app validates keys and values before writing a row.

### What it expects

- A SQLite database at the path defined by `DB_PATH` near the top of `InsetNIP.py` (update it to your local `foods.db`).
- The JSON object must include these fields (matching the `Foods` table, minus the auto-increment `FoodId`): `FoodDescription`, `Energy`, `Protein`, `FatTotal`, `SaturatedFat`, `TransFat`, `PolyunsaturatedFat`, `MonounsaturatedFat`, `Carbohydrate`, `Sugars`, `DietaryFibre`, `SodiumNa`, `CalciumCa`, `PotassiumK`, `ThiaminB1`, `RiboflavinB2`, `NiacinB3`, `Folate`, `IronFe`, `MagnesiumMg`, `VitaminC`, `Caffeine`, `Cholesterol`, `Alcohol`.
- Extra keys are rejected unless they are in `IGNORED_EXTRA_KEYS` (currently `notes`/`Notes`). Numeric `null` or `"null"` values are treated as `0.0`; a missing description becomes an empty string.

Example input (single record):

```json
{
  "FoodDescription": "Example food",
  "Energy": 123,
  "Protein": 4.5,
  "FatTotal": 2.1,
  "SaturatedFat": 0.5,
  "TransFat": 0,
  "PolyunsaturatedFat": 0.3,
  "MonounsaturatedFat": 1.0,
  "Carbohydrate": 20.4,
  "Sugars": 5.0,
  "DietaryFibre": 3.2,
  "SodiumNa": 210,
  "CalciumCa": 50,
  "PotassiumK": 80,
  "ThiaminB1": 0.1,
  "RiboflavinB2": 0.05,
  "NiacinB3": 0.8,
  "Folate": 12,
  "IronFe": 0.6,
  "MagnesiumMg": 15,
  "VitaminC": 6,
  "Caffeine": 0,
  "Cholesterol": 0,
  "Alcohol": 0,
  "notes": "optional free-form note (ignored)"
}
```

### Running InsetNIP

1. Edit `DB_PATH` in `InsetNIP.py` so it points to your `foods.db`.
2. Ensure the database exists (the app shows an error dialog and exits if the file is missing).
3. Launch the GUI:
   ```bash
   python InsetNIP.py
   ```
4. Paste a JSON object into the text box and click **Insert**. The app validates required keys, warns about unexpected keys, converts nulls to `0.0`, and inserts the row. Success and error messages appear as dialogs; the new `FoodId` is reported on success.

---

## Troubleshooting and tips

- Tkinter on Linux may require `sudo apt-get install python3-tk` (or your distro equivalent).
- If ChatBot shows "401" or "No API key provided", re-check `OPENAI_API_KEY` and restart the shell.
- For ChatBot tool errors mentioning `web_search`, leave it enabled (the app retries without tools automatically) or set `ENABLE_HOSTED_WEB_SEARCH = False` near the top of `ChatBot.py`.
- Image attachments work without Pillow; installing Pillow only improves thumbnails.
- `InsetNIP.py` performs client-side validation only. Make sure your `foods.db` schema matches the expected columns to avoid SQL errors.

---

## License

MIT - see `LICENSE`.
