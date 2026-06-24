#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import urllib.request
import urllib.parse
import urllib.error
import subprocess
import webbrowser
import termios
import tty
import shutil
import time
from datetime import datetime

# ANSI escape codes for beautiful formatting
CLEAR_SCREEN = "\033[2J\033[H"
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
UNDERLINE = "\033[4m"

# Colors (Modern Palette)
BLUE = "\033[38;5;75m"     # Sleek sky blue
CYAN = "\033[38;5;80m"     # Vibrant cyan
GREEN = "\033[38;5;120m"   # Light emerald green
YELLOW = "\033[38;5;220m"  # Warm yellow
ORANGE = "\033[38;5;208m"  # Soft orange
RED = "\033[38;5;203m"     # Soft red
MAGENTA = "\033[38;5;176m" # Soft magenta
GRAY = "\033[38;5;244m"    # Medium gray
LIGHT_GRAY = "\033[38;5;250m"

CONFIG_DIR = os.path.expanduser("~/.config/gtui")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

def load_config():
    if not os.path.exists(CONFIG_DIR):
        os.makedirs(CONFIG_DIR, exist_ok=True)
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "github_token": "",
        "github_user": "",
        "gitlab_token": "",
        "gitlab_user": "",
        "gitlab_host": "https://gitlab.com",
        "active_provider": "github"
    }

def save_config(config):
    if not os.path.exists(CONFIG_DIR):
        os.makedirs(CONFIG_DIR, exist_ok=True)
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"{RED}無法儲存設定檔: {e}{RESET}")

def api_request(url, method="GET", headers=None, data=None):
    if headers is None:
        headers = {}
    
    req_data = None
    if data is not None:
        if isinstance(data, dict):
            req_data = json.dumps(data).encode('utf-8')
            headers["Content-Type"] = "application/json"
        else:
            req_data = data
            
    req = urllib.request.Request(url, data=req_data, method=method)
    for k, v in headers.items():
        req.add_header(k, v)
        
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            resp_body = response.read().decode('utf-8')
            return json.loads(resp_body) if resp_body else {}, response.status
    except urllib.error.HTTPError as e:
        err_body = e.read().decode('utf-8')
        try:
            err_json = json.loads(err_body)
        except Exception:
            err_json = {"message": err_body}
        return err_json, e.code
    except Exception as e:
        return {"message": str(e)}, 500

def verify_github_token(token):
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "gtui-app"
    }
    res, status = api_request("https://api.github.com/user", headers=headers)
    if status == 200:
        return res.get("login"), res.get("name") or res.get("login")
    return None, None

def verify_gitlab_token(host, token):
    headers = {
        "Private-Token": token
    }
    host = host.rstrip('/')
    res, status = api_request(f"{host}/api/v4/user", headers=headers)
    if status == 200:
        return res.get("username"), res.get("name") or res.get("username")
    return None, None

def get_git_info():
    is_repo = False
    branch = "N/A"
    staged = 0
    unstaged = 0
    remote_url = "None"
    
    # Check if git command exists
    if not shutil.which("git"):
        return {
            "is_repo": False,
            "branch": "No Git CLI",
            "staged": 0,
            "unstaged": 0,
            "remote_url": "N/A"
        }
        
    if subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], capture_output=True, text=True).returncode == 0:
        is_repo = True
        
        # Get current branch
        res = subprocess.run(["git", "branch", "--show-current"], capture_output=True, text=True)
        branch = res.stdout.strip()
        if not branch:
            res = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True)
            branch = res.stdout.strip()
            if branch == "HEAD":
                branch = "分離標頭 (Detached)"
                
        # Get remote origin URL
        res = subprocess.run(["git", "remote", "get-url", "origin"], capture_output=True, text=True)
        if res.returncode == 0:
            remote_url = res.stdout.strip()
            
        # Get status info
        res = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
        for line in res.stdout.splitlines():
            if not line:
                continue
            status_code = line[:2]
            # Staged changes
            if status_code[0] in ['M', 'A', 'D', 'R', 'C']:
                staged += 1
            # Unstaged changes (modified or untracked)
            if status_code[1] in ['M', 'D'] or status_code == '??':
                unstaged += 1
                
    return {
        "is_repo": is_repo,
        "branch": branch,
        "staged": staged,
        "unstaged": unstaged,
        "remote_url": remote_url
    }

def print_header(config, git_info):
    term_width = shutil.get_terminal_size().columns
    print(CLEAR_SCREEN)
    
    logo = f"{BOLD}{BLUE}⚡ GTUI: 極簡終端 Git 控制台 ⚡{RESET}"
    user_status = f"{GRAY}未登入{RESET}"
    if config["active_provider"] == "github" and config["github_token"]:
        user_status = f"{GREEN}GitHub: {config['github_user']}{RESET}"
    elif config["active_provider"] == "gitlab" and config["gitlab_token"]:
        user_status = f"{GREEN}GitLab: {config['gitlab_user']}{RESET}"
        
    print(f" {logo}")
    print(f" {GRAY}─" * (term_width - 2) + RESET)
    
    cwd = os.getcwd()
    max_path_len = max(20, term_width - 45)
    if len(cwd) > max_path_len:
        cwd = "..." + cwd[-(max_path_len-3):]
        
    print(f" 📂 本地路徑: {CYAN}{cwd}{RESET} | 🔑 登入狀態: {user_status}")
    
    if git_info["is_repo"]:
        repo_status = f"{GREEN}已初始化 (分支: {git_info['branch']}){RESET}"
        changes = f"暫存: {GREEN}{git_info['staged']}{RESET} | 未暫存: {YELLOW}{git_info['unstaged']}{RESET}"
        remote = f"🔗 遠端倉庫: {CYAN}{git_info['remote_url']}{RESET}"
        print(f" 📦 Git 狀態: {repo_status} | {changes}")
        print(f" {remote}")
    else:
        print(f" 📦 Git 狀態: {RED}未初始化 Git 倉庫{RESET}")
        
    print(f" {GRAY}─" * (term_width - 2) + RESET)
    print()

def run_menu(options, config, title=None):
    selected_idx = 0
    fd = sys.stdin.fileno()
    
    while True:
        git_info = get_git_info()
        print_header(config, git_info)
        
        if title:
            print(f"  {BOLD}{YELLOW}::: {title} :::{RESET}\n")
            
        for idx, option in enumerate(options):
            if idx == selected_idx:
                print(f"  {CYAN}▶  {BOLD}{UNDERLINE}{option['name']}{RESET}")
            else:
                print(f"     {GRAY}{option['name']}{RESET}")
                
        print("\n" + f"  {GRAY}提示: [↑/↓] 移動，[Enter] 選擇，[q] 退出{RESET}")
        
        # Read keys in raw mode
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
            if ch == '\x1b':
                ch2 = sys.stdin.read(1)
                if ch2 == '[':
                    ch3 = sys.stdin.read(1)
                    if ch3 == 'A':    # Up
                        selected_idx = (selected_idx - 1) % len(options)
                    elif ch3 == 'B':  # Down
                        selected_idx = (selected_idx + 1) % len(options)
            elif ch.lower() == 'q':
                return None
            elif ch in ['\r', '\n']:
                return selected_idx
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

def run_command_live(cmd):
    print(f"{BOLD}{GRAY}執行指令: {' '.join(cmd)}{RESET}")
    try:
        # Run command and pipe output directly to stdout/stderr
        result = subprocess.run(cmd, check=False)
        return result.returncode
    except Exception as e:
        print(f"{RED}執行失敗: {e}{RESET}")
        return -1

def parse_git_remote(url):
    url_str = url.strip()
    if url_str.endswith(".git"):
        url_str = url_str[:-4]
        
    if url_str.startswith("http://") or url_str.startswith("https://"):
        parsed = urllib.parse.urlparse(url_str)
        path = parsed.path.lstrip('/')
        parts = path.split('/')
        if len(parts) >= 2:
            return parts[0], "/".join(parts[1:])
    elif url_str.startswith("git@"):
        parts = url_str.split(':')
        if len(parts) >= 2:
            path = parts[1]
            path_parts = path.split('/')
            if len(path_parts) >= 2:
                return path_parts[0], "/".join(path_parts[1:])
    return None, None

# --- Flows ---

def login_flow(config):
    print(f"{BOLD}{BLUE}=== 🔑 一鍵登入 ==={RESET}")
    print("1. GitHub")
    print("2. GitLab")
    choice = input("請選擇平台 (1-2, 預設 1): ").strip()
    if choice == "2":
        provider = "gitlab"
    else:
        provider = "github"
        
    if provider == "github":
        print(f"\n{GREEN}即將打開瀏覽器以生成 GitHub Personal Access Token (PAT)。{RESET}")
        print(f"請在瀏覽器中點選「Generate token」，然後將產生的 Token 複製回這裡。")
        input("請按 Enter 鍵開啟瀏覽器...")
        webbrowser.open("https://github.com/settings/tokens/new?scopes=repo,gist,write:org&description=gtui-token")
        
        token = input("\n請貼上您的 GitHub PAT: ").strip()
        if not token:
            print(f"{RED}Token 不能為空！{RESET}")
            return
            
        print("正在驗證 Token...")
        user, name = verify_github_token(token)
        if user:
            config["github_token"] = token
            config["github_user"] = user
            config["active_provider"] = "github"
            save_config(config)
            print(f"\n{GREEN}✔ 登入成功！ 歡迎, {name} ({user}){RESET}")
        else:
            print(f"\n{RED}❌ 驗證失敗，請檢查 Token 是否正確。{RESET}")
            
    elif provider == "gitlab":
        host = input("請輸入 GitLab 伺服器網址 (直接 Enter 預設為 https://gitlab.com): ").strip()
        if not host:
            host = "https://gitlab.com"
            
        print(f"\n{GREEN}即將打開瀏覽器以生成 GitLab Personal Access Token (PAT)。{RESET}")
        print(f"請在瀏覽器中點選「Create personal access token」，然後將產生的 Token 複製回這裡。")
        input("請按 Enter 鍵開啟瀏覽器...")
        webbrowser.open(f"{host.rstrip('/')}/-/profile/personal_access_tokens?scopes=api,write_repository,read_repository&name=gtui-token")
        
        token = input("\n請貼上您的 GitLab PAT: ").strip()
        if not token:
            print(f"{RED}Token 不能為空！{RESET}")
            return
            
        print("正在驗證 Token...")
        user, name = verify_gitlab_token(host, token)
        if user:
            config["gitlab_token"] = token
            config["gitlab_user"] = user
            config["gitlab_host"] = host
            config["active_provider"] = "gitlab"
            save_config(config)
            print(f"\n{GREEN}✔ 登入成功！ 歡迎, {name} ({user}){RESET}")
        else:
            print(f"\n{RED}❌ 驗證失敗，請檢查 Token 或 Host 是否正確。{RESET}")

def init_flow():
    print(f"{BOLD}{BLUE}=== 📁 初始化 Git 庫 ==={RESET}")
    git_info = get_git_info()
    if git_info["is_repo"]:
        ans = input(f"{YELLOW}目前資料夾已經是 Git 倉庫，是否要重新初始化？ (y/N): {RESET}").strip().lower()
        if ans != 'y':
            return
            
    rc = run_command_live(["git", "init"])
    if rc == 0:
        branch = input("請設定預設分支名稱 (預設: main): ").strip()
        if not branch:
            branch = "main"
        run_command_live(["git", "branch", "-M", branch])
        print(f"{GREEN}✔ 初始化成功！ 預設分支已設為 {branch}{RESET}")
    else:
        print(f"{RED}❌ 初始化失敗。{RESET}")

def change_remote_flow():
    print(f"{BOLD}{BLUE}=== 🔗 變更遠端 Repo 網址 ==={RESET}")
    git_info = get_git_info()
    if not git_info["is_repo"]:
        print(f"{RED}錯誤: 目前資料夾不是 Git 倉庫，請先初始化。{RESET}")
        return
        
    print(f"目前的遠端 Origin 網址: {CYAN}{git_info['remote_url']}{RESET}")
    url = input("請輸入新的遠端倉庫網址 (origin URL): ").strip()
    if not url:
        print("取消操作。")
        return
        
    # Check if origin exists
    res = subprocess.run(["git", "remote", "get-url", "origin"], capture_output=True)
    if res.returncode == 0:
        run_command_live(["git", "remote", "remove", "origin"])
        
    rc = run_command_live(["git", "remote", "add", "origin", url])
    if rc == 0:
        print(f"{GREEN}✔ 成功變更遠端倉庫為: {url}{RESET}")
    else:
        print(f"{RED}❌ 變更失敗。{RESET}")

def create_remote_repo(config, repo_name, is_private, description=""):
    provider = config["active_provider"]
    if provider == "github":
        token = config["github_token"]
        if not token:
            print(f"{RED}錯誤: 尚未登入 GitHub，請先登入。{RESET}")
            return None
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "gtui-app"
        }
        data = {
            "name": repo_name,
            "description": description,
            "private": is_private,
            "auto_init": False
        }
        print(f"正在 GitHub 上創建 Repo: {repo_name}...")
        res, status = api_request("https://api.github.com/user/repos", method="POST", headers=headers, data=data)
        if status == 201:
            return res.get("clone_url")
        else:
            print(f"{RED}創建失敗: {res.get('message')}{RESET}")
            return None
            
    elif provider == "gitlab":
        token = config["gitlab_token"]
        host = config["gitlab_host"].rstrip('/')
        if not token:
            print(f"{RED}錯誤: 尚未登入 GitLab，請先登入。{RESET}")
            return None
        headers = {
            "Private-Token": token
        }
        visibility = "private" if is_private else "public"
        data = {
            "name": repo_name,
            "description": description,
            "visibility": visibility,
            "initialize_with_readme": False
        }
        print(f"正在 GitLab ({host}) 上創建 Repo: {repo_name}...")
        res, status = api_request(f"{host}/api/v4/projects", method="POST", headers=headers, data=data)
        if status == 201:
            return res.get("http_url_to_repo")
        else:
            print(f"{RED}創建失敗: {res.get('message')}{RESET}")
            return None
            
    return None

def create_repo_flow(config):
    print(f"{BOLD}{BLUE}=== 🆕 創立新遠端 Repo ==={RESET}")
    provider = config["active_provider"]
    token = config["github_token"] if provider == "github" else config["gitlab_token"]
    if not token:
        print(f"{RED}錯誤: 您尚未登入 {provider.upper()}，請先執行一鍵登入。{RESET}")
        return
        
    default_name = os.path.basename(os.getcwd())
    repo_name = input(f"請輸入 Repo 名稱 (預設為當前目錄名 '{default_name}'): ").strip()
    if not repo_name:
        repo_name = default_name
        
    vis = input("是否設定為私有 (Private) 倉庫？ (Y/n): ").strip().lower()
    is_private = vis != 'n'
    
    desc = input("請輸入 Repo 簡介 (選填): ").strip()
    
    clone_url = create_remote_repo(config, repo_name, is_private, desc)
    if clone_url:
        print(f"\n{GREEN}✔ 成功在 {provider.upper()} 上創立倉庫！{RESET}")
        print(f"網址: {CYAN}{clone_url}{RESET}")
        
        git_info = get_git_info()
        if git_info["is_repo"]:
            ans = input(f"\n是否要將此 Repo 綁定為目前的 git remote origin？ (Y/n): ").strip().lower()
            if ans != 'n':
                res = subprocess.run(["git", "remote", "get-url", "origin"], capture_output=True)
                if res.returncode == 0:
                    subprocess.run(["git", "remote", "remove", "origin"])
                subprocess.run(["git", "remote", "add", "origin", clone_url])
                print(f"{GREEN}✔ 已設定 remote origin。{RESET}")

def push_flow(config):
    print(f"{BOLD}{BLUE}=== 🚀 一鍵暫存、提交並 Push ==={RESET}")
    git_info = get_git_info()
    if not git_info["is_repo"]:
        print(f"{RED}錯誤: 目前資料夾不是 Git 倉庫，請先初始化。{RESET}")
        return
        
    if git_info["staged"] == 0 and git_info["unstaged"] == 0:
        print(f"{YELLOW}目前沒有任何檔案變更。{RESET}")
        ans = input("是否要強制執行 git push 遠端同步？ (y/N): ").strip().lower()
        if ans != 'y':
            return
    else:
        # Prompt for what files to stage
        print(f"發現變更暫存狀況: 暫存={git_info['staged']}，未暫存={git_info['unstaged']}")
        ans = input("是否將所有檔案變更加入暫存？ (git add .) (Y/n): ").strip().lower()
        if ans != 'n':
            run_command_live(["git", "add", "."])
            
        commit_msg = input("請輸入 Commit 訊息 (直接 Enter 預設為時間戳): ").strip()
        if not commit_msg:
            commit_msg = f"Update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            
        run_command_live(["git", "commit", "-m", commit_msg])
        
    # Check remote origin
    git_info = get_git_info()
    if git_info["remote_url"] == "None":
        print(f"{RED}錯誤: 未設定遠端倉庫 (remote origin)！{RESET}")
        url = input("請輸入遠端 Repo 網址: ").strip()
        if not url:
            print("取消 Push。")
            return
        subprocess.run(["git", "remote", "add", "origin", url])
        
    # Check upstream
    branch = git_info["branch"]
    res = subprocess.run(["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], capture_output=True)
    if res.returncode != 0:
        # No upstream branch, set it
        print(f"{YELLOW}無上游分支，將設定上游並 Push...{RESET}")
        rc = run_command_live(["git", "push", "--set-upstream", "origin", branch])
    else:
        rc = run_command_live(["git", "push"])
        
    if rc == 0:
        print(f"\n{GREEN}✔ 一鍵 Push 成功！{RESET}")
    else:
        print(f"\n{RED}❌ Push 失敗，請確認網路與權限。{RESET}")

def delete_files_flow():
    print(f"{BOLD}{BLUE}=== 🗑️ 極簡刪除檔案 ==={RESET}")
    
    # Check if git is initialized
    git_info = get_git_info()
    
    files = []
    if git_info["is_repo"]:
        # Get files from git structure
        # Staged/unstaged tracked files
        res = subprocess.run(["git", "ls-files"], capture_output=True, text=True)
        if res.returncode == 0:
            for line in res.stdout.splitlines():
                if line:
                    files.append((line, True))
        # Untracked files
        res = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
        if res.returncode == 0:
            for line in res.stdout.splitlines():
                if line.startswith("?? "):
                    filepath = line[3:]
                    files.append((filepath, False))
        files = sorted(list(set(files)), key=lambda x: x[0])
    else:
        # Non-git directory: scan local files
        for root, dirs, filenames in os.walk("."):
            for filename in filenames:
                rel_path = os.path.relpath(os.path.join(root, filename), ".")
                if not rel_path.startswith(".git/") and rel_path != ".git":
                    files.append((rel_path, False))
        files = sorted(files, key=lambda x: x[0])
        
    if not files:
        print(f"{YELLOW}此目錄下沒有任何檔案。{RESET}")
        return
        
    selected = file_selector_tui(files, "選擇要刪除的檔案")
    if not selected:
        print("取消刪除。")
        return
        
    print(f"\n{BOLD}{RED}⚠️ 您已選擇刪除以下檔案:{RESET}")
    for item, tracked in selected:
        print(f"  - {item}")
        
    ans = input(f"\n{BOLD}{RED}確認要刪除這 {len(selected)} 個檔案？ (此動作無法復原！ 輸入 'y' 確認): {RESET}").strip().lower()
    if ans == 'y':
        for item, tracked in selected:
            try:
                if os.path.isdir(item):
                    shutil.rmtree(item)
                elif os.path.isfile(item):
                    if git_info["is_repo"] and tracked:
                        # git rm
                        subprocess.run(["git", "rm", "-f", item], capture_output=True)
                    else:
                        os.remove(item)
                print(f"{GRAY}已刪除: {item}{RESET}")
            except Exception as e:
                print(f"{RED}刪除失敗 {item}: {e}{RESET}")
        print(f"\n{GREEN}✔ 刪除程序完成。{RESET}")
    else:
        print("取消刪除。")

def file_selector_tui(files, title):
    selected_indices = set()
    cursor_idx = 0
    fd = sys.stdin.fileno()
    
    while True:
        term_height = shutil.get_terminal_size().lines
        max_display = max(5, term_height - 8)
        
        # Clear and draw TUI
        print(CLEAR_SCREEN)
        print(f"  {BOLD}{YELLOW}::: {title} :::{RESET}")
        print(f"  {GRAY}操作說明: [↑/↓] 移動，[Space] 勾選/取消，[a] 全選，[Enter] 確認，[q] 取消並返回{RESET}\n")
        
        start_idx = max(0, cursor_idx - max_display // 2)
        end_idx = min(len(files), start_idx + max_display)
        
        for idx in range(start_idx, end_idx):
            filepath, is_tracked = files[idx]
            prefix = "[*]" if idx in selected_indices else "[ ]"
            line_str = f" {prefix} {filepath} {'(已追蹤)' if is_tracked else '(未追蹤)'}"
            
            if idx == cursor_idx:
                print(f"  {CYAN}▶ {BOLD}{UNDERLINE}{line_str}{RESET}")
            else:
                print(f"    {GRAY}{line_str}{RESET}")
                
        if len(files) > max_display:
            print(f"\n  {GRAY}-- 顯示 {start_idx+1}-{end_idx} 筆，共 {len(files)} 筆 --{RESET}")
            
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
            if ch == '\x1b':
                ch2 = sys.stdin.read(1)
                if ch2 == '[':
                    ch3 = sys.stdin.read(1)
                    if ch3 == 'A':    # Up
                        cursor_idx = (cursor_idx - 1) % len(files)
                    elif ch3 == 'B':  # Down
                        cursor_idx = (cursor_idx + 1) % len(files)
            elif ch == ' ':
                if cursor_idx in selected_indices:
                    selected_indices.remove(cursor_idx)
                else:
                    selected_indices.add(cursor_idx)
            elif ch.lower() == 'a':
                if len(selected_indices) == len(files):
                    selected_indices.clear()
                else:
                    selected_indices = set(range(len(files)))
            elif ch in ['\r', '\n']:
                break
            elif ch.lower() == 'q':
                return []
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            
    return [files[idx] for idx in selected_indices]

def quick_create_push_flow(config):
    print(f"{BOLD}{BLUE}=== ⚡ 一鍵創建 Repo 並 Push 整個資料夾 ==={RESET}")
    provider = config["active_provider"]
    token = config["github_token"] if provider == "github" else config["gitlab_token"]
    if not token:
        print(f"{RED}錯誤: 您尚未登入 {provider.upper()}，請先登入。{RESET}")
        return
        
    default_name = os.path.basename(os.getcwd())
    repo_name = input(f"請輸入要創立的雲端 Repo 名稱 (預設為當前目錄名 '{default_name}'): ").strip()
    if not repo_name:
        repo_name = default_name
        
    vis = input("是否設定為私有 (Private) 倉庫？ (Y/n): ").strip().lower()
    is_private = vis != 'n'
    
    # 1. API Create
    clone_url = create_remote_repo(config, repo_name, is_private, f"Created via GTUI on {datetime.now()}")
    if not clone_url:
        print(f"{RED}❌ 雲端 Repo 創建失敗。{RESET}")
        return
        
    print(f"{GREEN}✔ 成功創立雲端 Repo: {clone_url}{RESET}")
    
    # 2. Local Init & Commit & Push
    git_info = get_git_info()
    if not git_info["is_repo"]:
        print("初始化本地 Git 倉庫...")
        subprocess.run(["git", "init"], capture_output=True)
        
    # Set default branch
    branch = "main"
    subprocess.run(["git", "branch", "-M", branch], capture_output=True)
    
    # Set remote
    subprocess.run(["git", "remote", "remove", "origin"], capture_output=True)
    subprocess.run(["git", "remote", "add", "origin", clone_url], capture_output=True)
    
    # Add, Commit, Push
    print("暫存所有檔案 (git add .)...")
    subprocess.run(["git", "add", "."])
    print("提交檔案...")
    subprocess.run(["git", "commit", "-m", "Initial commit via GTUI One-Click Setup"], capture_output=True)
    
    print("開始 Push 推送至雲端...")
    rc = run_command_live(["git", "push", "-u", "origin", branch])
    if rc == 0:
        print(f"\n{GREEN}🎉 一鍵創建並推送完成！{RESET}")
        print(f"您的倉庫網址: {CYAN}{clone_url}{RESET}")
    else:
        print(f"\n{RED}❌ 本地推送失敗，但雲端 Repo 已創立。請確認本地檔案及 Git 權限後手動 Push。{RESET}")

def quick_specify_push_flow(config):
    print(f"{BOLD}{BLUE}=== ⚡ 一鍵指定 Repo 並 Push 整個資料夾 ==={RESET}")
    url = input("請輸入要指定的遠端 Repo 網址 (HTTPS/SSH): ").strip()
    if not url:
        print("取消操作。")
        return
        
    # 1. Local Init
    git_info = get_git_info()
    if not git_info["is_repo"]:
        print("初始化本地 Git 倉庫...")
        subprocess.run(["git", "init"], capture_output=True)
        
    # Set default branch
    branch = "main"
    subprocess.run(["git", "branch", "-M", branch], capture_output=True)
    
    # Set remote
    subprocess.run(["git", "remote", "remove", "origin"], capture_output=True)
    subprocess.run(["git", "remote", "add", "origin", url], capture_output=True)
    
    # Add, Commit, Push
    print("暫存所有檔案 (git add .)...")
    subprocess.run(["git", "add", "."])
    print("提交檔案...")
    subprocess.run(["git", "commit", "-m", "Initial commit via GTUI One-Click Specify"], capture_output=True)
    
    print("開始 Push 推送至雲端...")
    rc = run_command_live(["git", "push", "-u", "origin", branch])
    if rc == 0:
        print(f"\n{GREEN}🎉 一鍵指定並推送完成！{RESET}")
    else:
        print(f"\n{RED}❌ 本地推送失敗，請確認遠端網址與 Git 權限後手動 Push。{RESET}")

def create_pr_flow(config):
    print(f"{BOLD}{BLUE}=== 🔀 建立 Pull Request (PR/MR) ==={RESET}")
    git_info = get_git_info()
    if not git_info["is_repo"]:
        print(f"{RED}錯誤: 目前資料夾不是 Git 倉庫。{RESET}")
        return
    if git_info["remote_url"] == "None":
        print(f"{RED}錯誤: 尚未綁定遠端倉庫，無法開 PR。{RESET}")
        return
        
    # Parse repo and owner
    owner, repo = parse_git_remote(git_info["remote_url"])
    if not owner or not repo:
        print(f"{RED}錯誤: 無法解析遠端倉庫名稱與擁有人 (URL: {git_info['remote_url']}){RESET}")
        return
        
    provider = config["active_provider"]
    token = config["github_token"] if provider == "github" else config["gitlab_token"]
    if not token:
        print(f"{RED}錯誤: 您尚未登入 {provider.upper()}，無法調用 API 開 PR。{RESET}")
        return
        
    # Get current branch
    head_branch = git_info["branch"]
    print(f"目前分支 (Head branch): {CYAN}{head_branch}{RESET}")
    
    base_branch = input("請輸入目標分支 (Base branch, 預設為 main): ").strip()
    if not base_branch:
        base_branch = "main"
        
    if head_branch == base_branch:
        print(f"{RED}錯誤: 起始分支不能與目標分支相同。{RESET}")
        return
        
    # Get default PR title (last commit message)
    default_title = ""
    res = subprocess.run(["git", "log", "-1", "--pretty=%B"], capture_output=True, text=True)
    if res.returncode == 0:
        default_title = res.stdout.strip().split('\n')[0]
        
    title = input(f"請輸入 PR 標題 (預設: {default_title}): ").strip()
    if not title:
        title = default_title
        
    body = input("請輸入 PR 描述 (選填): ").strip()
    
    print("\n正在向雲端平台發送 PR/MR 請求...")
    
    if provider == "github":
        url = f"https://api.github.com/repos/{owner}/{repo}/pulls"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "gtui-app"
        }
        data = {
            "title": title,
            "head": head_branch,
            "base": base_branch,
            "body": body
        }
        res, status = api_request(url, method="POST", headers=headers, data=data)
        if status == 201:
            pr_url = res.get("html_url")
            print(f"\n{GREEN}✔ PR 建立成功！{RESET}")
            print(f"PR 網址: {CYAN}{pr_url}{RESET}")
            webbrowser.open(pr_url)
        else:
            print(f"\n{RED}❌ 建立 PR 失敗: {res.get('message')}{RESET}")
            
    elif provider == "gitlab":
        host = config["gitlab_host"].rstrip('/')
        # URL encode project path
        encoded_project = urllib.parse.quote_plus(f"{owner}/{repo}")
        url = f"{host}/api/v4/projects/{encoded_project}/merge_requests"
        headers = {
            "Private-Token": token
        }
        data = {
            "source_branch": head_branch,
            "target_branch": base_branch,
            "title": title,
            "description": body
        }
        res, status = api_request(url, method="POST", headers=headers, data=data)
        if status == 201:
            mr_url = res.get("web_url")
            print(f"\n{GREEN}✔ Merge Request (MR) 建立成功！{RESET}")
            print(f"MR 網址: {CYAN}{mr_url}{RESET}")
            webbrowser.open(mr_url)
        else:
            print(f"\n{RED}❌ 建立 MR 失敗: {res.get('message')}{RESET}")

# --- Main Entry ---

def main():
    if not shutil.which("git"):
        print(f"{RED}錯誤: 本系統未安裝 git CLI，請先安裝 git。{RESET}")
        sys.exit(1)
        
    config = load_config()
    
    # Check if there is an active provider login on startup and set default if needed
    if config["github_token"]:
        config["active_provider"] = "github"
    elif config["gitlab_token"]:
        config["active_provider"] = "gitlab"
        
    menu_options = [
        {"name": "🔑 一鍵登入 (GitHub / GitLab)", "func": lambda: login_flow(config)},
        {"name": "📁 初始化 Git 倉庫 (git init)", "func": init_flow},
        {"name": "🔗 變更遠端 Repo 網址", "func": change_remote_flow},
        {"name": "🆕 在平台創立新 Repo", "func": lambda: create_repo_flow(config)},
        {"name": "🚀 一鍵暫存、提交並 Push", "func": lambda: push_flow(config)},
        {"name": "🗑️ 極簡刪除檔案", "func": delete_files_flow},
        {"name": "⚡ 一鍵創 Repo 並將整資料夾 Push 上去", "func": lambda: quick_create_push_flow(config)},
        {"name": "⚡ 一鍵指定 Repo 並將整資料夾 Push 上去", "func": lambda: quick_specify_push_flow(config)},
        {"name": "🔀 建立 Pull Request (PR / MR)", "func": lambda: create_pr_flow(config)},
        {"name": "❌ 結束退出", "func": None}
    ]
    
    try:
        while True:
            sel = run_menu(menu_options, config, "主選單")
            if sel is None or sel == len(menu_options) - 1:
                print(f"\n感謝使用 GTUI，再見！")
                break
                
            # Run selected action in cooked mode
            print(CLEAR_SCREEN)
            action_func = menu_options[sel]["func"]
            if action_func:
                try:
                    action_func()
                except KeyboardInterrupt:
                    print(f"\n{YELLOW}操作已中斷。{RESET}")
                except Exception as e:
                    print(f"\n{RED}執行時發生錯誤: {e}{RESET}")
                    
            print()
            input(f"{GRAY}請按 Enter 鍵返回主選單...{RESET}")
            
    except KeyboardInterrupt:
        print(f"\n\n感謝使用 GTUI，再見！")
        sys.exit(0)

if __name__ == "__main__":
    main()
