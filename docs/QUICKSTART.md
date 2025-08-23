# Quickstart

This is the fastest way to get **ChatBot.py** running.

## 1) Prerequisites
- Python **3.10+**
- `pip` available
- Tkinter installed (bundled on Windows/macOS via python.org installer; on Debian/Ubuntu: `sudo apt-get install -y python3-tk`)

## 2) Create a virtual environment
```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate
```

## 3) Install dependencies
```bash
pip install --upgrade pip
pip install openai tiktoken
```

## 4) Set your OpenAI API key
```powershell
# Windows PowerShell (persistent)
setx OPENAI_API_KEY "sk-...your-key..."
```
```cmd
:: Windows CMD (current shell only)
set OPENAI_API_KEY=sk-...your-key...
```
```bash
# macOS/Linux (current shell only)
export OPENAI_API_KEY="sk-...your-key..."
```

## 5) Run the app
```bash
python ChatBot.py
```

## 6) First run tips
- Use the **Model** combobox to select an available chat model.
- Type your **system prompt** on the right, then **Save System Prompt as** (e.g., `Default`).
- Start chatting on the left. Press **Enter** to send.
- Click **Show sources** to list links extracted from the last assistant reply.
- **NEW CHAT** resets to a fresh conversation using the current system prompt.
- Use **Save Chat as** to persist an entire transcript (stored as `system_prompts/<name>.chat.json`).

## Optional: Hosted Web Search
If your account/model supports a `web_search` tool, enable it in the source code:
```python
ENABLE_HOSTED_WEB_SEARCH = True
```
If a tool/model mismatch occurs, the app automatically retries without tools.

## Troubleshooting Essentials
- **401 Unauthorized** → API key not set/visible in the process.
- **No models listed** → check network/proxy; `pip show openai` should report a 1.x SDK.
- **Tkinter missing (Linux)** → `sudo apt-get install python3-tk`.
- **Window too big** → adjust `WINDOW_WIDTH`, `WINDOW_HEIGHT`, `WINDOW_W` near the file top.

— Happy hacking.
