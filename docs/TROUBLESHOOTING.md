# Troubleshooting

This page lists the most common issues encountered when running **ChatBot.py** and how to resolve them.

---

## 1) Authentication / API key issues

**Symptoms**
- `401 Unauthorized`
- “No API key provided”
- Requests fail immediately

**Checks**
1. Verify the environment variable is set for the shell that launches Python.
2. Confirm the key is valid and active for your account.
3. Ensure there are no stray quotes around the key in your shell profile.

**Fix**
```powershell
# Windows PowerShell (persistent)
setx OPENAI_API_KEY "sk-...your-key..."
# Restart terminal/app after setting
```
```cmd
:: Windows CMD (current shell only)
set OPENAI_API_KEY=sk-...your-key...
```
```bash
# macOS/Linux (current shell only)
export OPENAI_API_KEY="sk-...your-key..."
```

---

## 2) No models listed / “0 Chat Models”

**Symptoms**
- The combobox is empty or shows only a few non-chat models.

**Checks**
- `pip show openai` → ensure 1.x SDK is installed.
- Confirm network allows access to `models.list()` (corporate proxy/VPN may block).

**Fix**
```bash
pip install --upgrade openai
```

> The app filters out embeddings/audio/realtime/etc. It shows chat-capable models only.

---

## 3) Tool/model mismatch with `web_search`

**Symptoms**
- Error mentioning `web_search` tool not supported by the selected model or account.

**Good news**
- The app automatically retries *without tools*. This is a soft failure by design.

**Optional**
- Disable the feature in code:
```python
ENABLE_HOSTED_WEB_SEARCH = False
```

---

## 4) `tiktoken.encoding_for_model()` KeyError

**Symptoms**
- KeyError for unfamiliar/brand-new model IDs.

**Explanation**
- The code already falls back to `o200k_base` (long ctx) or `cl100k_base`.

**Action**
- None required; the fallback is expected and harmless.

---

## 5) Tkinter not found (Linux)

**Symptoms**
- ImportError for Tkinter.

**Fix (Debian/Ubuntu)**
```bash
sudo apt-get update
sudo apt-get install -y python3-tk
```

---

## 6) Window too large for your display

**Fix**
Edit these constants near the top of `ChatBot.py` and rerun:
```python
WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 950
WINDOW_W = 600
```

---

## 7) SSL / Proxy issues

**Symptoms**
- Requests hang or fail with SSL/handshake/proxy messages.

**Fixes**
- Try running outside a corporate proxy/VPN or configure system-wide proxy properly.
- On Windows, prefer the official Python from python.org.
- Verify that other Python HTTPS requests succeed (e.g., `pip install` or `requests.get`).

---

## 8) Saved files not where you expect

**Explanation**
- The app uses `Path.cwd()` for the `system_prompts/` location, i.e., the **current working directory** where you launch the script.

**Fix**
- Run from your repo root, or pin to the script folder by changing:
```python
# current behavior
self.base_dir = (Path.cwd() / "system_prompts").resolve()
# pin to script directory instead
self.base_dir = (Path(__file__).resolve().parent / "system_prompts").resolve()
```

---

## 9) Threading + UI updates

**Symptoms**
- UI feels frozen; errors related to thread-unsafe calls.

**Notes**
- `get_bot_response` runs on a background thread.
- UI updates are done by appending text in a thread-safe manner.
- If you extend the app with long operations, prefer `after()` callbacks to update the UI safely.

---

## Diagnostic tips

- Print exceptions in `get_bot_response` (already done).
- Add temporary logging around `responses.create()` calls.
- Use a small test prompt and a tiny message to isolate model/tool problems.
