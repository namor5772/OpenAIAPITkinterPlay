# Architecture

This document explains the key modules/classes, how requests are built, where files are stored, and how large histories are summarized.

---

## Components

### 1) `ChatMemoryBot`
- Wraps the **OpenAI Responses API** client.
- Maintains `chat_history` (list of `{role, content}` dicts).
- Counts tokens via **tiktoken** and triggers summarization when thresholds are exceeded.
- Builds the request, optionally including a `web_search` tool.
- Extracts URLs from both the raw structured response *and* the assistant text.

**Important fields**
- `default_model` / `browse_model`: synchronized to the UI’s model selection.
- `str_system_prompt`: the current system message.
- `max_tokens`: token budget for the whole chat history (default 20,000).

**Key methods**
- `_build_request()` – prepares the payload, adding tools only when enabled.
- `_summarize_history(old_messages)` – uses the default (non-browsing) model to compress earlier turns into a single assistant “Summary” message.
- `_extract_citations(resp, reply_text)` – finds URLs inside structured fields and free text.

### 2) `ChatbotApp` (Tkinter UI)
- Manages all widgets, file I/O, and state persistence.
- Left pane: transcript. Right pane: system prompt editor.
- Top controls: model combobox, save/load/delete for prompts, chat session management.

**State & persistence**
- **System prompts** are plain `.txt` files in `system_prompts/`.
- **Chat sessions** are `.chat.json` in the same folder.
- `.textpad_state.json` remembers the last opened prompt and chat.
- On exit, unnamed sessions are autosaved to `_autosave.chat.json`.

---

## Request Flow

1. `send_message()` captures user text and spawns a background thread.
2. `get_bot_response()` calls `bot.ask(user_input)`:
   - Ensures the current system prompt is the first message.
   - Optionally includes a `web_search` tool.
   - Falls back to a non-tool request if the tool isn’t supported.
3. The assistant reply and extracted sources are appended to the transcript.

---

## Token Management & Summarization

- Token count is computed across all messages in `chat_history`.
- When count exceeds `max_tokens`:
  1. Keep the **system message** and the **last 10 messages**.
  2. Summarize all **older** messages into one assistant message.
  3. Replace history accordingly and continue.

This preserves recency while retaining context in compressed form.

---

## File/Directory Layout

```
repo-root-or-launch-dir/
├─ ChatBot.py
├─ .textpad_state.json          # last prompt/chat state
└─ system_prompts/
   ├─ <name>.txt                # saved system prompts
   ├─ <name>.chat.json          # saved chat sessions
   └─ _autosave.chat.json       # autosave for unnamed sessions
```

> The app uses `Path.cwd()`. If you prefer to pin to the script directory, see **Troubleshooting → Saved files not where you expect**.

---

## Threading Model & UI Responsiveness

- Background work runs in a `threading.Thread` to keep Tk’s event loop responsive.
- UI updates are done on the main thread via Tkinter methods.
- If you add long tasks (downloads, parsing), prefer:
  - periodic progress updates via `after()`
  - cancel buttons/flags
  - timeouts and retries around network calls

---

## Design Choices (opinionated)

- **Plain Tkinter** for portability; no external UI frameworks.
- **Simple file format** for prompts and chats for easy inspection and versioning.
- **Hosted web search tool** is optional and non-breaking (auto-fallback).
- **Summarization** happens automatically so the UI stays fast and chats don’t error out under heavy histories.
