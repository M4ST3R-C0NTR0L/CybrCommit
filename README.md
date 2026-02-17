# 🤖 ai-commit

[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![GitHub stars](https://img.shields.io/github/stars/M4ST3R-C0NTR0L/ai-commit?style=social)](https://github.com/M4ST3R-C0NTR0L/ai-commit)

> Never write a commit message again.

**ai-commit** generates perfect [Conventional Commits](https://www.conventionalcommits.org/) for your git changes. It works **without any API keys** using a smart rule-based engine, with optional AI enhancement via OpenAI, Anthropic, or local Ollama.

---

## ✨ Quick Start

```bash
pip install ai-commit-cli
ai-commit
```

That's it. No setup, no API keys, no configuration files.

---

## 🚀 Demo

```bash
$ git diff --staged
```
```diff
diff --git a/src/auth/login.js b/src/auth/login.js
new file mode 100644
index 0000000..abc1234
--- /dev/null
+++ b/src/auth/login.js
@@ -0,0 +1,45 @@
+import { useState } from 'react';
+
+export function LoginForm() {
+  const [email, setEmail] = useState('');
+  const [password, setPassword] = useState('');
+
+  const handleSubmit = async (e) => {
+    e.preventDefault();
+    await login(email, password);
+  };
+
+  return (
+    <form onSubmit={handleSubmit}>
+      <input type="email" value={email} onChange={e => setEmail(e.target.value)} />
+      <input type="password" value={password} onChange={e => setPassword(e.target.value)} />
+      <button type="submit">Login</button>
+    </form>
+  );
+}
```

```bash
$ ai-commit

📁 1 file changed
   +45 additions, -0 deletions

   Files:
   ➕ src/auth/login.js

🤔 Generating commit message...

💬 Generated commit message:
   feat(auth): add login form component

Commit? [y]es, [e]dit, [r]egenerate, [n]o: y

✅ Committed: feat(auth): add login form component
```

---

## 📦 Installation

```bash
# Using pip
pip install ai-commit-cli

# Using pipx (recommended)
pipx install ai-commit-cli

# Using uv
uv tool install ai-commit-cli
```

---

## 🎯 Features

- ✅ **Zero-config mode** — Works immediately, no API keys needed
- ✅ **Smart rule-based engine** — Analyzes diff patterns intelligently
- ✅ **Conventional Commits** — Always follows the spec
- ✅ **AI enhancement** — Optional OpenAI, Anthropic, or Ollama support
- ✅ **Interactive mode** — Review, edit, or regenerate before committing
- ✅ **Auto mode** — Skip confirmation for CI/CD workflows
- ✅ **Gitmoji support** — Add expressive emoji to commits
- ✅ **File type detection** — Understands tests, docs, configs, dependencies
- ✅ **Smart truncation** — Handles huge diffs gracefully

---

## 📖 Usage

### Interactive Mode (Default)

```bash
ai-commit
```

Shows the generated message and asks for confirmation.

### Auto Mode

```bash
ai-commit --auto
```

Commits without asking. Perfect for scripts and CI/CD.

### Dry Run

```bash
ai-commit --dry
```

Shows what the message would be without committing.

### Stage All

```bash
ai-commit --all
```

Stage all changes first, then commit.

### Custom Scope

```bash
ai-commit --scope api
# Result: feat(api): ...
```

### Override Type

```bash
ai-commit --type fix
# Forces "fix:" instead of auto-detecting
```

### Add Emoji

```bash
ai-commit --emoji
# Result: ✨ feat: add new feature
```

---

## 🧠 Rule-Based Engine

The built-in engine is smart enough for most projects:

| Change Pattern | Generated Message |
|----------------|-------------------|
| New file added | `feat: add filename` |
| File deleted | `chore: remove filename` |
| File renamed | `refactor: rename old to new` |
| Test files | `test: add tests for...` |
| Config files | `chore: update config` |
| README/docs | `docs: update documentation` |
| Dependencies | `chore: update dependencies` |
| CSS/styles | `style: update styles` |
| Multiple files | Summarized intelligently |

---

## 🤖 AI Providers (Optional)

For even better messages, connect an AI provider:

### OpenAI

```bash
export OPENAI_API_KEY="sk-..."
ai-commit --ai openai
```

### Anthropic

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
ai-commit --ai anthropic
```

### Ollama (Local)

```bash
# Start Ollama locally
ollama run llama3.2

# Use local AI
ai-commit --ai ollama
```

---

## ⚙️ Configuration

### Environment Variables

```bash
# AI Providers
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
export OLLAMA_HOST="http://localhost:11434"

# Default settings
export AI_COMMIT_PROVIDER="openai"      # openai | anthropic | ollama
export AI_COMMIT_MODEL="gpt-4o-mini"    # any valid model
export AI_COMMIT_EMOJI="1"              # enable emoji by default
export AI_COMMIT_AUTO="1"               # auto-commit by default
export AI_COMMIT_MAX_DIFF_LINES="500"   # truncate large diffs
```

### Config File

Create `~/.config/ai-commit/config`:

```bash
# AI provider (optional)
provider=openai
model=gpt-4o-mini

# Default behavior
emoji=true
auto=false
max_diff_lines=500
```

---

## 📊 Before vs After

### Before ai-commit

```
commit 3f4a9b2c
Author: developer@example.com
Date:   Mon Jan 15 10:30:00 2025

    updated stuff

commit 8e7d6f5a
Author: developer@example.com
Date:   Mon Jan 15 09:15:00 2025

    fix

commit 1a2b3c4d
Author: developer@example.com
Date:   Fri Jan 12 16:45:00 2025

    WIP
```

### After ai-commit

```
commit 9b8c7d6e
Author: developer@example.com
Date:   Mon Jan 15 10:30:00 2025

    feat(auth): add OAuth2 login with Google provider

commit 5f4e3d2c
Author: developer@example.com
Date:   Mon Jan 15 09:15:00 2025

    fix(api): resolve race condition in user cache

commit 7a6b5c4d
Author: developer@example.com
Date:   Fri Jan 12 16:45:00 2025

    test(utils): add unit tests for date formatting helpers
```

---

## 🔧 CLI Reference

```
ai-commit [OPTIONS]

Options:
  -h, --help            Show help message
  -v, --version         Show version
  --auto                Auto-commit without confirmation
  --dry                 Show message only, don't commit
  -a, --all             Stage all changes before committing
  --scope SCOPE         Specify commit scope
  --type TYPE           Override commit type (feat, fix, docs, etc.)
  --ai PROVIDER         Use AI provider (openai, anthropic, ollama)
  --model MODEL         Specify AI model
  -e, --emoji           Add gitmoji to commit
  --no-emoji            Disable emoji
  -m, --message MSG     Use custom message
```

---

## 🛠️ Development

```bash
# Clone the repository
git clone https://github.com/M4ST3R-C0NTR0L/ai-commit.git
cd ai-commit

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or: venv\Scripts\activate on Windows

# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black ai_commit/
isort ai_commit/

# Type check
mypy ai_commit/
```

---

## 📋 Requirements

- Python 3.8+
- Git

**Optional:**
- `openai` package for OpenAI support
- `anthropic` package for Anthropic support
- Ollama running locally for local AI

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'feat: add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- Inspired by the [Conventional Commits](https://www.conventionalcommits.org/) specification
- Gitmoji support based on [gitmoji](https://gitmoji.dev/)

---

<p align="center">
  Built by <a href="https://github.com/M4ST3R-C0NTR0L">Cybrflux</a>
</p>
