# Agent Air

這個 repo 是個人 AI agent 設定的跨電腦同步來源。目標是切換到其他電腦時，只要 clone 此 repo，就能恢復一致、可審查且不含機密的 agent 環境。

重點包括：

- 共用與 agent-specific skills
- Hermes、Claude Code、Codex、Cursor、OpenCode、Gemini 的非機密設定
- MCP server 定義（token 改成環境變數 placeholder）
- 快照、安裝與機密掃描腳本

## 目錄

```text
configs/                 經過 sanitization 的 agent 設定
  hermes/
  claude/
  codex/
  cursor/
  opencode/
  gemini/
skills/
  shared/                canonical 共用 skills（來自 ~/.agents/skills）
  hermes/                Hermes-specific skills
  claude|codex|.../      各 agent 額外的 local skills
manifests/inventory.json 目前安裝結構清單
scripts/snapshot.py      從本機重新產生快照
scripts/install.py       在新機器安裝；預設只 dry-run
scripts/check-secrets.py 提交前掃描疑似機密
private/                 本機私密設定（被 gitignore；不會建立或提交）
```

`manifests/inventory.json` 的 `skills` 是去重後 repo 實際保存的 skill names；`source_skills` 則記錄快照當下各 agent 原始目錄中的 local／symlink 狀態。

> `skills/hermes` 不包含 Hermes 的 `.hub` index/cache、curator backups 或其他 runtime state；Codex 內建 `.system` skills 也不納入版本控制。這些應由各工具本身安裝或更新。

## 快照本機設定

```bash
python3 scripts/snapshot.py
python3 scripts/check-secrets.py
```

只更新 configs／manifest，不重新複製 skills：

```bash
python3 scripts/snapshot.py --configs-only
```

`snapshot.py` 會：

1. 將 `~/.agents/skills` 放到 `skills/shared`。
2. 保存各 agent 非 symlink 的額外 skills；只要 skill frontmatter 的 `name` 已存在於 shared，就移除 agent-specific 副本，即使內容略有差異。
3. 若相同 skill 同時出現在至少兩個 agent 且整個目錄內容完全相同，自動提升到 `skills/shared`，各 agent 安裝時改用 symlink。
4. 保存 MCP 與主要設定。
5. 將敏感欄位改成 `${ENV_VAR}`，並把 home path 改成 `~`。

這是防呆，不是完整的秘密管理器；每次 commit 前仍應執行 `check-secrets.py` 並人工檢查 diff。

## 從某台電腦回寫更新到 repo

當某台電腦上的 agent、MCP 或 skills 有更新時，先讓本機 repo 跟遠端同步，再擷取本機狀態：

```bash
cd ~/Documents/GitHub/agent-air
git pull --rebase
python3 scripts/snapshot.py
python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 scripts/check-secrets.py
git diff --check
git status --short
git diff
```

人工確認 diff 沒有 token、OAuth credential、session 或 cache 後，再提交：

```bash
git add -A
git commit -m "chore: sync agent settings"
git push
```

### Shared skill 更新

正常安裝後，各 agent 的共用 skill 都是指向 `~/.agents/skills/<name>` 的 symlink。若 agent 直接更新 symlink 指向的內容，只要執行上面的 `snapshot.py` 即可回寫到 `skills/shared`。

先確認是否仍是 symlink：

```bash
readlink ~/.claude/skills/<skill-name>
readlink ~/.codex/skills/<skill-name>
```

若 agent 的 updater 把 symlink 換成了自己的實體目錄，而且 shared 已有同名 skill，`skills/shared` 仍是 canonical；請先比較並將想保留的新版本更新到 `~/.agents/skills/<skill-name>`，再執行 snapshot：

```bash
diff -ru ~/.agents/skills/<skill-name> ~/.claude/skills/<skill-name>
# 確認 Claude 的版本才是要保留的版本後：
rsync -a --delete ~/.claude/skills/<skill-name>/ ~/.agents/skills/<skill-name>/
python3 scripts/snapshot.py
```

不要在未檢查 diff 前使用 `rsync --delete`。如果同名 skill 的兩個版本都需要保留，應先改其中一個 skill frontmatter 的 `name`，讓它成為真正的 agent-specific skill。

### 在其他電腦套用最新設定

```bash
cd ~/Documents/GitHub/agent-air
git pull --rebase
python3 scripts/install.py          # 先 dry-run
python3 scripts/install.py --apply  # 安裝 skills
```

若也要套用 configs：

```bash
python3 scripts/install.py --configs --apply
```

## 安裝到另一台電腦

先看 dry-run：

```bash
python3 scripts/install.py
```

確認後安裝 skills：

```bash
python3 scripts/install.py --apply
```

連 sanitized configs 一起安裝：

```bash
python3 scripts/install.py --configs --apply
```

安裝器會將被取代的路徑備份成 `*.agent-air.bak`。共用 skills 安裝到 `~/.agents/skills`，各 agent 一律以相對 symlink 使用 shared 版本；repo 若仍有同名 agent-specific 副本，安裝器會停止並要求先重新執行 snapshot。Hermes 自有 skills 與共用 symlink 會一起安裝。

## 機密資訊怎麼處理

### 推薦：公開 config 只引用環境變數

Hermes MCP 支援 `${VAR}` 和 `${env:VAR}`，例如：

```yaml
mcp_servers:
  github:
    command: npx
    args: ["-y", "@modelcontextprotocol/server-github"]
    env:
      GITHUB_PERSONAL_ACCESS_TOKEN: "${GITHUB_TOKEN}"
```

HTTP MCP：

```yaml
mcp_servers:
  internal:
    url: https://mcp.example.com/mcp
    headers:
      Authorization: "Bearer ${INTERNAL_MCP_TOKEN}"
```

Hermes 的 secret scope 是 `~/.hermes/.env`（active profile 時則在該 profile 的 `.env`）。這個檔案不要提交。

### OAuth MCP

對 `auth: oauth` 的 server，不要搬 token。Hermes 將 token 保存在 `~/.hermes/mcp-tokens/<server>.json`；新電腦執行：

```bash
hermes mcp login <server>
```

### Agent 能不能讀 gitignored config？

**可以。** `.gitignore` 只控制 Git tracking，不是存取權限。只要 agent 的 sandbox/approval policy 允許，`read_file`、shell 或程式仍能讀 repo 內的 `private/...`。

建議做法：

```text
private/
  hermes.env
  cursor.mcp.local.json
```

- `private/` 已在 `.gitignore`。
- 用 `git check-ignore -v private/hermes.env` 驗證。
- 不要在 `AGENTS.md`、skill 或 prompt 中貼出 secret。
- 不要依賴 ignore 作安全邊界；若 agent 不應看見秘密，請用 macOS Keychain、1Password CLI、受限 shell wrapper 或 MCP OAuth，並只在執行時注入。

範例：

```bash
mkdir -p private
cp .env.example private/hermes.env
chmod 600 private/hermes.env
```

## 驗證

```bash
python3 scripts/check-secrets.py
git status --short
git diff --check
```

若要確認 ignore：

```bash
git check-ignore -v private/hermes.env .env
```

## 目前 MCP 摘要

Hermes 的三個 MCP 都是 OAuth 型態，因此 repo 只保存 server URL 與 `auth: oauth`：

- Atlassian
- Context7
- Figma

OAuth token 不在此 repo；新機器需重新登入。
