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
    # Make sure starting index is not a header
    while selected_idx < len(options) and options[selected_idx].get("is_header"):
        selected_idx += 1
        
    fd = sys.stdin.fileno()
    
    while True:
        git_info = get_git_info()
        print_header(config, git_info)
        
        if title:
            print(f"  {BOLD}{YELLOW}::: {title} :::{RESET}\n")
            
        for idx, option in enumerate(options):
            if option.get("is_header"):
                print(f"  {BOLD}{MAGENTA}─── {option['name']} ───{RESET}")
            elif idx == selected_idx:
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
                        while True:
                            selected_idx = (selected_idx - 1) % len(options)
                            if not options[selected_idx].get("is_header"):
                                break
                    elif ch3 == 'B':  # Down
                        while True:
                            selected_idx = (selected_idx + 1) % len(options)
                            if not options[selected_idx].get("is_header"):
                                break
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
def ensure_gitignore():
    git_info = get_git_info()
    if not git_info["is_repo"]:
        return

    gitignore_path = ".gitignore"
    common_ignores = [
        "node_modules/",
        "__pycache__/",
        "*.pyc",
        "*.pyo",
        "*.pyd",
        ".venv/",
        "venv/",
        "env/",
        "dist/",
        "build/",
        "target/",
        ".idea/",
        ".vscode/",
        ".DS_Store",
        "Thumbs.db",
        ".env",
        "*.log"
    ]
    
    existing_lines = []
    if os.path.exists(gitignore_path):
        try:
            with open(gitignore_path, 'r', encoding='utf-8') as f:
                existing_lines = [line.strip() for line in f.read().splitlines()]
        except Exception:
            pass

    to_add = []
    for pattern in common_ignores:
        if pattern not in existing_lines:
            to_add.append(pattern)
            
    if to_add:
        try:
            needs_leading_newline = False
            if os.path.exists(gitignore_path) and os.path.getsize(gitignore_path) > 0:
                with open(gitignore_path, 'rb') as f_bin:
                    try:
                        f_bin.seek(-1, 2)
                        last_char = f_bin.read(1)
                        if last_char != b'\n':
                            needs_leading_newline = True
                    except Exception:
                        pass
            
            with open(gitignore_path, 'a', encoding='utf-8') as f:
                if needs_leading_newline:
                    f.write('\n')
                f.write("# Added automatically by GTUI\n")
                for pattern in to_add:
                    f.write(f"{pattern}\n")
            print(f"{GREEN}✔ 已自動將 {', '.join(to_add)} 加入 .gitignore{RESET}")
        except Exception as e:
            print(f"{RED}無法更新 .gitignore: {e}{RESET}")

def https_to_ssh_url(url):
    if url.startswith("git@") or "ssh://" in url:
        return url
        
    parsed = urllib.parse.urlparse(url)
    domain = parsed.netloc
    
    if "@" in domain:
        domain = domain.split("@")[-1]
        
    port = None
    if ":" in domain:
        domain_parts = domain.split(":")
        domain = domain_parts[0]
        port = domain_parts[1]
        
    path = parsed.path.lstrip('/')
    if not path.endswith(".git"):
        path = path + ".git"
        
    if port:
        return f"ssh://git@{domain}:{port}/{path}"
    else:
        return f"git@{domain}:{path}"

def get_or_create_ssh_key(username):
    ssh_dir = os.path.expanduser("~/.ssh")
    os.makedirs(ssh_dir, exist_ok=True)
    
    possible_keys = ["id_ed25519.pub", "id_rsa.pub", "id_ecdsa.pub", "id_dsa.pub"]
    for k in possible_keys:
        path = os.path.join(ssh_dir, k)
        if os.path.exists(path):
            return path
            
    key_path = os.path.join(ssh_dir, "id_ed25519")
    pub_key_path = key_path + ".pub"
    print("正在生成新的 Ed25519 SSH 金鑰...")
    rc_gen = subprocess.run(
        ["ssh-keygen", "-t", "ed25519", "-N", "", "-f", key_path, "-C", f"{username}@gtui"],
        capture_output=True
    ).returncode
    if rc_gen == 0:
        subprocess.run(["ssh-add", key_path], capture_output=True)
        return pub_key_path
    return None

def check_and_handle_remote_updates(config):
    print("正在檢查遠端是否有新 Commit...")
    # 1. Fetch remote tracking branch info
    res_fetch = subprocess.run(["git", "fetch"], capture_output=True)
    if res_fetch.returncode != 0:
        print(f"{YELLOW}⚠️ 無法更新遠端分支資訊 (git fetch 失敗)。{RESET}")
        return True
        
    # 2. Check if HEAD is behind remote tracking branch
    res_count = subprocess.run(["git", "rev-list", "--count", "HEAD..@{u}"], capture_output=True, text=True)
    if res_count.returncode != 0:
        return True
        
    try:
        count = int(res_count.stdout.strip())
    except ValueError:
        count = 0
        
    if count == 0:
        print(f"{GREEN}✔ 遠端無新 Commit，本地分支已是最新。{RESET}")
        return True
        
    print(f"{YELLOW}偵測到遠端有新 commit (共 {count} 個)，正在嘗試自動 Pull 並 Rebase...{RESET}")
    
    # 3. Perform pull --rebase
    rc_pull = run_command_live(["git", "pull", "--rebase"])
    if rc_pull == 0:
        print(f"{GREEN}✔ 自動 Pull & Rebase 成功！{RESET}")
        return True
        
    # 4. If pull --rebase fails, check if we are in conflict (rebase in progress)
    git_dir_res = subprocess.run(["git", "rev-parse", "--git-dir"], capture_output=True, text=True)
    if git_dir_res.returncode == 0:
        git_dir = git_dir_res.stdout.strip()
        rebase_merge = os.path.join(git_dir, "rebase-merge")
        rebase_apply = os.path.join(git_dir, "rebase-apply")
        
        if os.path.exists(rebase_merge) or os.path.exists(rebase_apply):
            while True:
                print(f"\n{RED}❌ Pull & Rebase 發生衝突！{RESET}")
                print(f"{YELLOW}請手動解決衝突。{RESET}")
                print(f"1. 已手動解決衝突，繼續 Rebase (git rebase --continue)")
                print(f"2. 放棄 Rebase (git rebase --abort)")
                print(f"3. 暫時返回主選單 (稍後手動處理)")
                
                choice = input("請選擇操作 (1-3): ").strip()
                if choice == '1':
                    rc_continue = run_command_live(["git", "rebase", "--continue"])
                    if rc_continue == 0:
                        print(f"{GREEN}✔ Rebase 成功完成！{RESET}")
                        return True
                    else:
                        if os.path.exists(rebase_merge) or os.path.exists(rebase_apply):
                            print(f"{YELLOW}仍然存在衝突或 Rebase 尚未完成。{RESET}")
                            continue
                        else:
                            print(f"{RED}Rebase 失敗。{RESET}")
                            return False
                elif choice == '2':
                    subprocess.run(["git", "rebase", "--abort"])
                    print(f"{YELLOW}已取消 Rebase。{RESET}")
                    return False
                elif choice == '3':
                    print(f"{YELLOW}已暫停處理。您可以在終端手動執行 git rebase --continue 解決衝突。{RESET}")
                    return False
                else:
                    print("無效的選擇。")
        else:
            print(f"{RED}❌ Pull & Rebase 失敗。{RESET}")
            return False
    else:
        print(f"{RED}❌ Pull & Rebase 失敗。{RESET}")
        return False

def run_push_with_fallback(config, cmd):
    rc = run_command_live(cmd)
    if rc == 0:
        return 0
        
    git_info = get_git_info()
    remote_url = git_info["remote_url"]
    
    if remote_url == "None" or not (remote_url.startswith("http://") or remote_url.startswith("https://")):
        return rc
        
    print(f"\n{YELLOW}⚠️ 檢測到 HTTPS 傳輸失敗，是否要切換至 SSH 傳輸大檔案？{RESET}")
    ans = input("是否切換至 SSH 傳輸？ (Y/n): ").strip().lower()
    if ans == 'n':
        return rc
        
    # Determine provider from the remote URL domain
    parsed_url = urllib.parse.urlparse(remote_url)
    domain = parsed_url.netloc
    if "@" in domain:
        domain = domain.split("@")[-1]
    if ":" in domain:
        domain = domain.split(":")[0]

    if "gitlab" in domain.lower():
        provider = "gitlab"
    elif "github" in domain.lower():
        provider = "github"
    else:
        provider = config.get("active_provider", "github")
    
    # 1. Ask for username
    username = config.get(f"{provider}_user")
    if not username:
        username = input(f"請輸入您的 {provider.upper()} 使用者名稱 (username): ").strip()
        if username:
            config[f"{provider}_user"] = username
            save_config(config)
            
    if not username:
        print(f"{RED}錯誤: 未提供使用者名稱，無法繼續。{RESET}")
        return rc
        
    # 2. Check SSH key status
    ssh_ok = False
    print(f"正在檢查與 git@{domain} 的 SSH 連線...")
    try:
        res = subprocess.run(
            ["ssh", "-o", "StrictHostKeyChecking=accept-new", "-o", "ConnectTimeout=5", "-T", f"git@{domain}"],
            capture_output=True, text=True
        )
        output = res.stdout + res.stderr
        if "successfully authenticated" in output or "Welcome to GitLab" in output or "Welcome to" in output:
            ssh_ok = True
            print(f"{GREEN}✔ SSH 連線成功。{RESET}")
    except Exception as e:
        print(f"{RED}檢查 SSH 連線時發生錯誤: {e}{RESET}")
        
    if not ssh_ok:
        print(f"{YELLOW}未檢測到有效的 SSH 金鑰設定或 SSH 測試失敗。{RESET}")
        ans_key = input("是否自動為您生成並在雲端設定 SSH 金鑰？ (Y/n): ").strip().lower()
        if ans_key != 'n':
            token = config.get(f"{provider}_token")
            if not token:
                print(f"{RED}您尚未登入此平台，無法自動上傳 SSH 金鑰。請先在主選單執行登入。{RESET}")
                return rc
                
            pub_key_path = get_or_create_ssh_key(username)
            if pub_key_path:
                try:
                    with open(pub_key_path, 'r', encoding='utf-8') as f:
                        pub_key_content = f.read().strip()
                        
                    print(f"正在上傳 SSH 金鑰至您的 {provider.upper()} 帳戶...")
                    title = f"GTUI SSH Key ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})"
                    
                    if provider == "github":
                        url = "https://api.github.com/user/keys"
                        headers = {
                            "Authorization": f"Bearer {token}",
                            "Accept": "application/vnd.github+json",
                            "User-Agent": "gtui-app"
                        }
                        data = {"title": title, "key": pub_key_content}
                        res, status = api_request(url, method="POST", headers=headers, data=data)
                        if status == 201:
                            print(f"{GREEN}✔ 成功將 SSH 金鑰新增至 GitHub！{RESET}")
                            ssh_ok = True
                        else:
                            print(f"{RED}❌ 無法上傳金鑰至 GitHub: {res.get('message')}{RESET}")
                    elif provider == "gitlab":
                        host = config.get("gitlab_host", "https://gitlab.com").rstrip('/')
                        url = f"{host}/api/v4/user/keys"
                        headers = {"Private-Token": token}
                        data = {"title": title, "key": pub_key_content}
                        res, status = api_request(url, method="POST", headers=headers, data=data)
                        if status == 201:
                            print(f"{GREEN}✔ 成功將 SSH 金鑰新增至 GitLab！{RESET}")
                            ssh_ok = True
                        else:
                            print(f"{RED}❌ 無法上傳金鑰至 GitLab: {res.get('message')}{RESET}")
                except Exception as e:
                    print(f"{RED}上傳金鑰時出錯: {e}{RESET}")
            else:
                return rc
                
    # 3. Convert remote URL to SSH
    ssh_url = https_to_ssh_url(remote_url)
    print(f"正在將遠端倉庫網址變更為 SSH: {CYAN}{ssh_url}{RESET}")
    subprocess.run(["git", "remote", "set-url", "origin", ssh_url])
    
    # 4. Retry push
    print("正在使用 SSH 重新嘗試推送...")
    rc_retry = run_command_live(cmd)
    if rc_retry == 0:
        print(f"{GREEN}✔ 使用 SSH 重新推送成功！{RESET}")
        return 0
    else:
        print(f"{RED}❌ 使用 SSH 重新推送仍失敗。將恢復為原遠端網址。{RESET}")
        subprocess.run(["git", "remote", "set-url", "origin", remote_url])
        return rc_retry

def clone_flow(config):
    print(f"{BOLD}{BLUE}=== 📥 一鍵 Clone 遠端倉庫 ==={RESET}")
    print(f"將會 Clone 至當前目錄: {CYAN}{os.getcwd()}{RESET}")
    url = input("請輸入要 Clone 的遠端 Repo 網址 (HTTPS/SSH): ").strip()
    if not url:
        print("取消操作。")
        return
        
    print(f"正在 Clone 倉庫: {url} ...")
    rc = run_command_live(["git", "clone", url])
    if rc == 0:
        print(f"\n{GREEN}✔ Clone 成功！{RESET}")
        return
        
    # Check if URL was HTTPS and clone failed
    if not (url.startswith("http://") or url.startswith("https://")):
        print(f"\n{RED}❌ Clone 失敗，請確認網址或權限。{RESET}")
        return
        
    print(f"\n{YELLOW}⚠️ 檢測到 HTTPS Clone 失敗，是否嘗試切換至 SSH Clone 傳輸？{RESET}")
    ans = input("是否切換至 SSH 傳輸？ (Y/n): ").strip().lower()
    if ans == 'n':
        return
        
    # Parse domain
    parsed_url = urllib.parse.urlparse(url)
    domain = parsed_url.netloc
    if "@" in domain:
        domain = domain.split("@")[-1]
    if ":" in domain:
        domain = domain.split(":")[0]
        
    if "gitlab" in domain.lower():
        provider = "gitlab"
    elif "github" in domain.lower():
        provider = "github"
    else:
        provider = config.get("active_provider", "github")
        
    # 1. Ask for username
    username = config.get(f"{provider}_user")
    if not username:
        username = input(f"請輸入您的 {provider.upper()} 使用者名稱 (username): ").strip()
        if username:
            config[f"{provider}_user"] = username
            save_config(config)
            
    if not username:
        print(f"{RED}錯誤: 未提供使用者名稱，無法繼續。{RESET}")
        return
        
    # 2. Check SSH key status
    ssh_ok = False
    print(f"正在檢查與 git@{domain} 的 SSH 連線...")
    try:
        res = subprocess.run(
            ["ssh", "-o", "StrictHostKeyChecking=accept-new", "-o", "ConnectTimeout=5", "-T", f"git@{domain}"],
            capture_output=True, text=True
        )
        output = res.stdout + res.stderr
        if "successfully authenticated" in output or "Welcome to GitLab" in output or "Welcome to" in output:
            ssh_ok = True
            print(f"{GREEN}✔ SSH 連線成功。{RESET}")
    except Exception as e:
        print(f"{RED}檢查 SSH 連線時發生錯誤: {e}{RESET}")
        
    if not ssh_ok:
        print(f"{YELLOW}未檢測到有效的 SSH 金鑰設定或 SSH 測試失敗。{RESET}")
        ans_key = input("是否自動為您生成並在雲端設定 SSH 金鑰？ (Y/n): ").strip().lower()
        if ans_key != 'n':
            token = config.get(f"{provider}_token")
            if not token:
                print(f"{RED}您尚未登入此平台，無法自動上傳 SSH 金鑰。請先在主選單執行登入。{RESET}")
                return
                
            pub_key_path = get_or_create_ssh_key(username)
            if pub_key_path:
                try:
                    with open(pub_key_path, 'r', encoding='utf-8') as f:
                        pub_key_content = f.read().strip()
                        
                    print(f"正在上傳 SSH 金鑰至您的 {provider.upper()} 帳戶...")
                    title = f"GTUI SSH Key ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})"
                    
                    if provider == "github":
                        headers = {
                            "Authorization": f"Bearer {token}",
                            "Accept": "application/vnd.github+json",
                            "User-Agent": "gtui-app"
                        }
                        data = {"title": title, "key": pub_key_content}
                        res, status = api_request("https://api.github.com/user/keys", method="POST", headers=headers, data=data)
                        if status == 201:
                            print(f"{GREEN}✔ 成功將 SSH 金鑰新增至 GitHub！{RESET}")
                            ssh_ok = True
                        else:
                            print(f"{RED}❌ 無法上傳金鑰至 GitHub: {res.get('message')}{RESET}")
                    elif provider == "gitlab":
                        host = config.get("gitlab_host", "https://gitlab.com").rstrip('/')
                        headers = {"Private-Token": token}
                        data = {"title": title, "key": pub_key_content}
                        res, status = api_request(f"{host}/api/v4/user/keys", method="POST", headers=headers, data=data)
                        if status == 201:
                            print(f"{GREEN}✔ 成功將 SSH 金鑰新增至 GitLab！{RESET}")
                            ssh_ok = True
                        else:
                            print(f"{RED}❌ 無法上傳金鑰至 GitLab: {res.get('message')}{RESET}")
                except Exception as e:
                    print(f"{RED}上傳金鑰時出錯: {e}{RESET}")
            else:
                return
                
    if ssh_ok:
        # Convert url to SSH
        ssh_url = https_to_ssh_url(url)
        print(f"正在使用 SSH 網址重新嘗試 Clone: {CYAN}{ssh_url}{RESET}")
        rc_retry = run_command_live(["git", "clone", ssh_url])
        if rc_retry == 0:
            print(f"\n{GREEN}✔ 使用 SSH Clone 成功！{RESET}")
        else:
            print(f"\n{RED}❌ 使用 SSH Clone 仍失敗。{RESET}")
    else:
        print(f"\n{RED}❌ 無法完成 SSH 設定，Clone 失敗。{RESET}")

def quick_push_existing_flow(config):
    print(f"{BOLD}{BLUE}=== 🚀 一鍵 Push 推送到此目錄的遠端倉庫 ==={RESET}")
    git_info = get_git_info()
    if not git_info["is_repo"]:
        print(f"{RED}錯誤: 目前資料夾不是 Git 倉庫，請先初始化。{RESET}")
        return
        
    ensure_gitignore()
    git_info = get_git_info()
        
    # Check if there are changes (staged or unstaged)
    if git_info["staged"] > 0 or git_info["unstaged"] > 0:
        print(f"偵測到未提交的變更 (暫存: {git_info['staged']}, 未暫存: {git_info['unstaged']})。")
        ans = input("是否要將這些變更一併暫存、提交並 Push 推送？ (Y/n): ").strip().lower()
        if ans != 'n':
            run_command_live(["git", "add", "."])
            commit_msg = input("請輸入 Commit 訊息 (直接 Enter 預設為時間戳): ").strip()
            if not commit_msg:
                commit_msg = f"Update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            run_command_live(["git", "commit", "-m", commit_msg])
            # Refresh status
            git_info = get_git_info()
            
    # Check remote origin
    if git_info["remote_url"] == "None":
        print(f"{YELLOW}目前尚未設定遠端倉庫 (remote origin)。{RESET}")
        url = input("請輸入遠端 Repo 網址 (HTTPS/SSH): ").strip()
        if not url:
            print("已取消操作。")
            return
        subprocess.run(["git", "remote", "add", "origin", url])
        git_info = get_git_info()
        
    branch = git_info["branch"]
    res = subprocess.run(["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], capture_output=True)
    if res.returncode != 0:
        print(f"{YELLOW}無上游分支，將設定上游並 Push...{RESET}")
        rc = run_push_with_fallback(config, ["git", "push", "--set-upstream", "origin", branch])
    else:
        if not check_and_handle_remote_updates(config):
            print(f"\n{RED}❌ 由於 Rebase 未完成或被取消，已中止 Push。{RESET}")
            return
        rc = run_push_with_fallback(config, ["git", "push"])
        
    if rc == 0:
        print(f"\n{GREEN}✔ 一鍵 Push 成功！{RESET}")
    else:
        print(f"\n{RED}❌ Push 推送失敗。{RESET}")

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
        ensure_gitignore()
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
        
    ensure_gitignore()
    # Re-evaluate git info since .gitignore might have been added/modified
    git_info = get_git_info()
        
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
        rc = run_push_with_fallback(config, ["git", "push", "--set-upstream", "origin", branch])
    else:
        if not check_and_handle_remote_updates(config):
            print(f"\n{RED}❌ 由於 Rebase 未完成或被取消，已中止 Push。{RESET}")
            return
        rc = run_push_with_fallback(config, ["git", "push"])
        
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
        
    ensure_gitignore()
    
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
    rc = run_push_with_fallback(config, ["git", "push", "-u", "origin", branch])
    if rc == 0:
        print(f"\n{GREEN}🎉 一鍵創建並推送完成！{RESET}")
        git_info = get_git_info()
        print(f"您的倉庫網址: {CYAN}{git_info['remote_url']}{RESET}")
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
        
    ensure_gitignore()
        
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
    rc = run_push_with_fallback(config, ["git", "push", "-u", "origin", branch])
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

def add_collaborator_flow(config):
    print(f"{BOLD}{BLUE}=== 👥 新增協作者 (Collaborator) ==={RESET}")
    git_info = get_git_info()
    if not git_info["is_repo"]:
        print(f"{RED}錯誤: 目前資料夾不是 Git 倉庫。{RESET}")
        return
    if git_info["remote_url"] == "None":
        print(f"{RED}錯誤: 尚未綁定遠端倉庫，無法新增協作者。{RESET}")
        return
        
    # Parse repo and owner
    owner, repo = parse_git_remote(git_info["remote_url"])
    if not owner or not repo:
        print(f"{RED}錯誤: 無法解析遠端倉庫名稱與擁有人 (URL: {git_info['remote_url']}){RESET}")
        return
        
    provider = config["active_provider"]
    token = config["github_token"] if provider == "github" else config["gitlab_token"]
    if not token:
        print(f"{RED}錯誤: 您尚未登入 {provider.upper()}，無法調用 API 新增協作者。{RESET}")
        return

    if provider == "github":
        username = input("請輸入要加入的 GitHub 帳號: ").strip()
        if not username:
            print("取消操作。")
            return
            
        print(f"正在將 {username} 新增至 {owner}/{repo} 協作者清單...")
        
        url = f"https://api.github.com/repos/{owner}/{repo}/collaborators/{username}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "gtui-app"
        }
        data = {"permission": "push"}
        res, status = api_request(url, method="PUT", headers=headers, data=data)
        
        if status in [201, 204]:
            if status == 201:
                print(f"\n{GREEN}✔ 成功邀請協作者 {username}！邀請函已發送。{RESET}")
                invite_url = res.get("html_url")
                if invite_url:
                    print(f"邀請接受網址: {CYAN}{invite_url}{RESET}")
            else:
                print(f"\n{GREEN}✔ 使用者 {username} 已經是此倉庫的協作者。{RESET}")
        else:
            print(f"\n{RED}❌ 新增協作者失敗: {res.get('message')}{RESET}")
            
    elif provider == "gitlab":
        username = input("請輸入要加入的 GitLab 帳號: ").strip()
        if not username:
            print("取消操作。")
            return
            
        host = config["gitlab_host"].rstrip('/')
        print(f"正在查詢 GitLab 使用者 {username} 的 ID...")
        
        user_url = f"{host}/api/v4/users?username={username}"
        headers = {
            "Private-Token": token
        }
        user_res, user_status = api_request(user_url, method="GET", headers=headers)
        
        if user_status != 200 or not isinstance(user_res, list) or len(user_res) == 0:
            print(f"\n{RED}❌ 找不到 GitLab 使用者 {username}。{RESET}")
            return
            
        user_id = user_res[0].get("id")
        print(f"使用者 ID: {user_id}，正在新增至專案成員清單...")
        
        encoded_project = urllib.parse.quote_plus(f"{owner}/{repo}")
        url = f"{host}/api/v4/projects/{encoded_project}/members"
        
        data = {
            "user_id": user_id,
            "access_level": 30
        }
        res, status = api_request(url, method="POST", headers=headers, data=data)
        if status == 201:
            print(f"\n{GREEN}✔ 成功將 {username} 新增為專案成員 (Developer 權限)！{RESET}")
        else:
            print(f"\n{RED}❌ 新增專案成員失敗: {res.get('message')}{RESET}")

def branch_management_flow():
    print(f"{BOLD}{BLUE}=== 🌿 分支管理 ==={RESET}")
    git_info = get_git_info()
    if not git_info["is_repo"]:
        print(f"{RED}錯誤: 目前資料夾不是 Git 倉庫。{RESET}")
        return

    # Get branches
    res = subprocess.run(["git", "branch", "--format=%(refname:short)"], capture_output=True, text=True)
    if res.returncode != 0:
        print(f"{RED}無法獲取分支資訊。{RESET}")
        return
        
    branches = [b.strip() for b in res.stdout.splitlines() if b.strip()]
    if not branches:
        print(f"{YELLOW}目前沒有任何分支。{RESET}")
        return
        
    current_res = subprocess.run(["git", "branch", "--show-current"], capture_output=True, text=True)
    current_branch = current_res.stdout.strip()
    if not current_branch:
        res_ref = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True)
        current_branch = res_ref.stdout.strip()
    
    branch_options = []
    for b in branches:
        suffix = " (目前分支)" if b == current_branch else ""
        branch_options.append({"name": f"🌿 {b}{suffix}", "branch_name": b})
    branch_options.append({"name": "🆕 建立新分支 (Create New Branch)", "branch_name": "__create__"})
    branch_options.append({"name": "⬅️ 返回主選單", "branch_name": "__back__"})
    
    fd = sys.stdin.fileno()
    selected_idx = 0
    
    while True:
        print_header(load_config(), git_info)
        print(f"  {BOLD}{YELLOW}::: 🌿 本地分支清單 ::: {RESET}\n")
        for idx, opt in enumerate(branch_options):
            if idx == selected_idx:
                print(f"  {CYAN}▶  {BOLD}{UNDERLINE}{opt['name']}{RESET}")
            else:
                print(f"     {GRAY}{opt['name']}{RESET}")
        print("\n" + f"  {GRAY}提示: [↑/↓] 移動，[Enter] 選擇，[q] 返回{RESET}")
        
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
            if ch == '\x1b':
                ch2 = sys.stdin.read(1)
                if ch2 == '[':
                    ch3 = sys.stdin.read(1)
                    if ch3 == 'A':    # Up
                        selected_idx = (selected_idx - 1) % len(branch_options)
                    elif ch3 == 'B':  # Down
                        selected_idx = (selected_idx + 1) % len(branch_options)
            elif ch.lower() == 'q':
                return
            elif ch in ['\r', '\n']:
                break
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            
    chosen = branch_options[selected_idx]
    branch_name = chosen["branch_name"]
    
    if branch_name == "__back__":
        return
        
    if branch_name == "__create__":
        print(CLEAR_SCREEN)
        print(f"{BOLD}{BLUE}=== 🆕 建立新分支 ==={RESET}")
        new_branch = input("請輸入新分支名稱: ").strip()
        if not new_branch:
            print("已取消。")
            return
        rc = run_command_live(["git", "checkout", "-b", new_branch])
        if rc == 0:
            print(f"{GREEN}✔ 成功建立並切換至新分支: {new_branch}{RESET}")
        return
        
    # Branch actions menu
    print(CLEAR_SCREEN)
    print(f"{BOLD}{BLUE}=== 🌿 分支操作: {branch_name} ==={RESET}")
    print(f"1. 切換至此分支 (git checkout {branch_name})")
    print(f"2. 刪除此分支 (git branch -d {branch_name})")
    print(f"3. 合併此分支到目前分支 (git merge {branch_name})")
    print(f"4. 取消")
    
    act = input("請選擇操作 (1-4): ").strip()
    if act == '1':
        rc = run_command_live(["git", "checkout", branch_name])
        if rc == 0:
            print(f"{GREEN}✔ 成功切換至分支 {branch_name}{RESET}")
    elif act == '2':
        if branch_name == current_branch:
            print(f"{RED}錯誤: 無法刪除目前所在的分支。請先切換至其他分支。{RESET}")
            return
        rc = run_command_live(["git", "branch", "-d", branch_name])
        if rc != 0:
            ans = input(f"{YELLOW}普通刪除失敗，是否強制刪除？ (y/N): {RESET}").strip().lower()
            if ans == 'y':
                run_command_live(["git", "branch", "-D", branch_name])
    elif act == '3':
        ans = input(f"確認要將 {branch_name} 合併到目前分支 {current_branch} 嗎？ (y/N): ").strip().lower()
        if ans == 'y':
            run_command_live(["git", "merge", branch_name])

def commit_history_flow():
    print(f"{BOLD}{BLUE}=== 📜 提交歷史 (Commit History) ==={RESET}")
    git_info = get_git_info()
    if not git_info["is_repo"]:
        print(f"{RED}錯誤: 目前資料夾不是 Git 倉庫。{RESET}")
        return
        
    cmd = ["git", "log", "-n", "15", "--oneline", "--decorate", "--color"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"{RED}無法取得提交歷史。{RESET}")
        return
        
    output = res.stdout.strip()
    if not output:
        print(f"{YELLOW}目前此分支沒有任何提交紀錄。{RESET}")
        return
        
    print(f"\n{BOLD}{YELLOW}::: 最近 15 次 Commit 紀錄 ::: {RESET}")
    print(output)

def view_issues_flow(config):
    print(f"{BOLD}{BLUE}=== 📋 專案 Issue 追蹤 ==={RESET}")
    git_info = get_git_info()
    if not git_info["is_repo"]:
        print(f"{RED}錯誤: 目前資料夾不是 Git 倉庫。{RESET}")
        return
    if git_info["remote_url"] == "None":
        print(f"{RED}錯誤: 尚未設定遠端倉庫，無法讀取 Issue。{RESET}")
        return
        
    owner, repo = parse_git_remote(git_info["remote_url"])
    if not owner or not repo:
        print(f"{RED}錯誤: 無法解析遠端倉庫名稱與擁有人 (URL: {git_info['remote_url']}){RESET}")
        return
        
    provider = config["active_provider"]
    token = config["github_token"] if provider == "github" else config["gitlab_token"]
    if not token:
        print(f"{RED}錯誤: 您尚未登入 {provider.upper()}，無法調用 API 查看 Issue。{RESET}")
        return

    print("正在從雲端平台獲取 Open Issues 列表...")
    if provider == "github":
        url = f"https://api.github.com/repos/{owner}/{repo}/issues?state=open&per_page=15"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "gtui-app"
        }
        res, status = api_request(url, headers=headers)
        if status != 200:
            print(f"{RED}無法取得 Issue 列表: {res.get('message', '未知錯誤')}{RESET}")
            return
            
        issues = [i for i in res if "pull_request" not in i]
        
        if not issues:
            print(f"{GREEN}✔ 太棒了！此倉庫目前沒有任何 Open Issues。{RESET}")
            return
            
        print(f"\n{BOLD}{YELLOW}::: {owner}/{repo} Open Issues (最近 15 筆) ::: {RESET}")
        for i in issues:
            num = i.get("number")
            title = i.get("title")
            user = i.get("user", {}).get("login", "unknown")
            created_at = i.get("created_at", "")[:10]
            print(f"  {CYAN}#{num}{RESET} - {BOLD}{title}{RESET} ({GRAY}由 {user} 於 {created_at} 建立{RESET})")
            
    elif provider == "gitlab":
        host = config["gitlab_host"].rstrip('/')
        encoded_project = urllib.parse.quote_plus(f"{owner}/{repo}")
        url = f"{host}/api/v4/projects/{encoded_project}/issues?state=opened&per_page=15"
        headers = {
            "Private-Token": token
        }
        res, status = api_request(url, headers=headers)
        if status != 200:
            print(f"{RED}無法取得 Issue 列表: {res.get('message', '未知錯誤')}{RESET}")
            return
            
        if not res:
            print(f"{GREEN}✔ 太棒了！此倉庫目前沒有任何 Open Issues。{RESET}")
            return
            
        print(f"\n{BOLD}{YELLOW}::: {owner}/{repo} Open Issues (最近 15 筆) ::: {RESET}")
        for i in res:
            num = i.get("iid")
            title = i.get("title")
            user = i.get("author", {}).get("username", "unknown")
            created_at = i.get("created_at", "")[:10]
            print(f"  {CYAN}#{num}{RESET} - {BOLD}{title}{RESET} ({GRAY}由 {user} 於 {created_at} 建立{RESET})")

def view_collaborators_flow(config):
    print(f"{BOLD}{BLUE}=== 👥 查看協作者清單 ==={RESET}")
    git_info = get_git_info()
    if not git_info["is_repo"]:
        print(f"{RED}錯誤: 目前資料夾不是 Git 倉庫。{RESET}")
        return
    if git_info["remote_url"] == "None":
        print(f"{RED}錯誤: 尚未設定遠端倉庫，無法讀取協作者。{RESET}")
        return
        
    owner, repo = parse_git_remote(git_info["remote_url"])
    if not owner or not repo:
        print(f"{RED}錯誤: 無法解析遠端倉庫名稱與擁有人 (URL: {git_info['remote_url']}){RESET}")
        return
        
    provider = config["active_provider"]
    token = config["github_token"] if provider == "github" else config["gitlab_token"]
    if not token:
        print(f"{RED}錯誤: 您尚未登入 {provider.upper()}，無法調用 API 查看協作者。{RESET}")
        return

    print("正在從雲端平台獲取協作者列表...")
    if provider == "github":
        url = f"https://api.github.com/repos/{owner}/{repo}/collaborators"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "gtui-app"
        }
        res, status = api_request(url, headers=headers)
        if status != 200:
            print(f"{RED}無法取得協作者列表: {res.get('message', '未知錯誤')}{RESET}")
            return
            
        print(f"\n{BOLD}{YELLOW}::: {owner}/{repo} 協作者清單 ::: {RESET}")
        for c in res:
            login = c.get("login")
            role_name = c.get("role_name", "collaborator")
            print(f"  👤 {BOLD}{login}{RESET} ({CYAN}{role_name}{RESET})")
            
    elif provider == "gitlab":
        host = config["gitlab_host"].rstrip('/')
        encoded_project = urllib.parse.quote_plus(f"{owner}/{repo}")
        url = f"{host}/api/v4/projects/{encoded_project}/members"
        headers = {
            "Private-Token": token
        }
        res, status = api_request(url, headers=headers)
        if status != 200:
            print(f"{RED}無法取得成員列表: {res.get('message', '未知錯誤')}{RESET}")
            return
            
        print(f"\n{BOLD}{YELLOW}::: {owner}/{repo} 成員清單 ::: {RESET}")
        levels = {10: "Guest", 20: "Reporter", 30: "Developer", 40: "Maintainer", 50: "Owner"}
        for m in res:
            username = m.get("username")
            access_level = m.get("access_level")
            role_name = levels.get(access_level, f"Level {access_level}")
            print(f"  👤 {BOLD}{username}{RESET} ({CYAN}{role_name}{RESET})")

def commit_graph_flow():
    print(f"{BOLD}{BLUE}=== 🌿 分支樹狀圖 (Commit Graph) ==={RESET}")
    git_info = get_git_info()
    if not git_info["is_repo"]:
        print(f"{RED}錯誤: 目前資料夾不是 Git 倉庫。{RESET}")
        return
        
    cmd = [
        "git", "log", "--graph", "--all", "--color",
        "--format=format:%C(bold blue)%h%C(reset) - %C(bold green)(%ar)%C(reset) %C(white)%s%C(reset) %C(bold yellow)%d%C(reset)"
    ]
    res = subprocess.run(cmd + ["-n", "30"], capture_output=True, text=True)
    if res.returncode != 0:
        print(f"{RED}無法取得分支圖。{RESET}")
        return
        
    output = res.stdout
    if not output.strip():
        print(f"{YELLOW}目前倉庫無任何 commit。{RESET}")
        return
        
    print(f"\n{BOLD}{YELLOW}::: 顯示最近 30 筆 Commit 樹狀圖 ::: {RESET}\n")
    print(output)

def interactive_staging_flow():
    print(f"{BOLD}{BLUE}=== 🔍 暫存區與檔案差異管理 ==={RESET}")
    git_info = get_git_info()
    if not git_info["is_repo"]:
        print(f"{RED}錯誤: 目前資料夾不是 Git 倉庫。{RESET}")
        return
        
    fd = sys.stdin.fileno()
    
    while True:
        res = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
        if res.returncode != 0:
            print(f"{RED}無法取得暫存狀態。{RESET}")
            return
            
        lines = res.stdout.splitlines()
        files = []
        for line in lines:
            if len(line) >= 4:
                status_code = line[:2]
                filepath = line[3:].strip('"')
                files.append((filepath, status_code))
                
        if not files:
            print(f"{GREEN}✔ 目前沒有任何未提交的檔案變更。{RESET}")
            return
            
        cursor_idx = 0
        while True:
            term_height = shutil.get_terminal_size().lines
            max_display = max(5, term_height - 8)
            
            print(CLEAR_SCREEN)
            print(f"  {BOLD}{YELLOW}::: 🔍 檔案暫存與 Diff 管理 :::{RESET}")
            print(f"  {GRAY}操作說明: [↑/↓] 移動，[Space] 暫存/取消暫存，[d] 查看該檔 Diff，[Enter/q] 返回{RESET}\n")
            
            start_idx = max(0, cursor_idx - max_display // 2)
            end_idx = min(len(files), start_idx + max_display)
            
            for idx in range(start_idx, end_idx):
                filepath, status_code = files[idx]
                is_staged = status_code[0] in ['M', 'A', 'D', 'R', 'C']
                
                check = "[✓]" if is_staged else "[ ]"
                
                if status_code == '??':
                    color = RED
                    lbl = "新增未追蹤"
                elif status_code[0] == 'A':
                    color = GREEN
                    lbl = "已暫存新增"
                elif status_code[0] == 'M':
                    color = GREEN
                    lbl = "已暫存修改"
                elif status_code[1] == 'M':
                    color = YELLOW
                    lbl = "未暫存修改"
                elif status_code[0] == 'D':
                    color = RED
                    lbl = "已暫存刪除"
                elif status_code[1] == 'D':
                    color = RED
                    lbl = "未暫存刪除"
                else:
                    color = CYAN
                    lbl = "有變更"
                    
                line_str = f" {check} {color}{filepath:<30}{RESET} {GRAY}({lbl}){RESET}"
                
                if idx == cursor_idx:
                    print(f"  {CYAN}▶ {BOLD}{UNDERLINE}{line_str}{RESET}")
                else:
                    print(f"    {line_str}")
                    
            if len(files) > max_display:
                print(f"\n  {GRAY}-- 顯示 {start_idx+1}-{end_idx} 筆，共 {len(files)} 筆 --{RESET}")
                
            old_settings = termios.tcgetattr(fd)
            action = None
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
                    action = "toggle"
                elif ch.lower() == 'd':
                    action = "diff"
                elif ch in ['\r', '\n', 'q', 'Q']:
                    action = "exit"
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
                
            if action == "exit":
                return
            elif action == "toggle":
                filepath, status_code = files[cursor_idx]
                is_staged = status_code[0] in ['M', 'A', 'D', 'R', 'C']
                if is_staged:
                    subprocess.run(["git", "restore", "--staged", filepath])
                else:
                    subprocess.run(["git", "add", filepath])
                break
            elif action == "diff":
                filepath, status_code = files[cursor_idx]
                print(CLEAR_SCREEN)
                print(f"{BOLD}{BLUE}=== 🔍 變更差異: {filepath} ==={RESET}\n")
                
                is_staged = status_code[0] in ['M', 'A', 'D', 'R', 'C']
                if status_code == '??':
                    print(f"{YELLOW}此檔案為全新未追蹤檔案，尚無 Diff 比對紀錄。{RESET}")
                else:
                    diff_cmd = ["git", "diff", "--color"]
                    if is_staged:
                        diff_cmd.append("--cached")
                    diff_cmd.append(filepath)
                    diff_res = subprocess.run(diff_cmd, capture_output=True, text=True)
                    print(diff_res.stdout)
                    
                input(f"\n{GRAY}請按 Enter 鍵返回列表...{RESET}")

def stash_management_flow():
    while True:
        print(CLEAR_SCREEN)
        print(f"{BOLD}{BLUE}=== 📦 Stash 暫存進度管理 ==={RESET}\n")
        
        res_list = subprocess.run(["git", "stash", "list"], capture_output=True, text=True)
        stash_output = res_list.stdout.strip()
        if stash_output:
            print(f"{BOLD}{YELLOW}目前已有的 Stash 暫存紀錄：{RESET}")
            print(f"{CYAN}{stash_output}{RESET}\n")
        else:
            print(f"{GRAY}(目前無任何暫存紀錄){RESET}\n")
            
        print("1. ➕ 新增工作區暫存 (Stash current changes)")
        print("2. 🔄 恢復最近的暫存並移除紀錄 (Stash Pop)")
        print("3. 📋 套用最近的暫存並保留紀錄 (Stash Apply)")
        print("4. 🗑️ 刪除最近的暫存紀錄 (Stash Drop)")
        print("5. 💥 清空所有暫存紀錄 (Stash Clear)")
        print("6. ⬅️ 返回主選單")
        
        choice = input("\n請選擇操作 (1-6): ").strip()
        if choice == '1':
            msg = input("請輸入暫存備註訊息 (選填): ").strip()
            cmd = ["git", "stash", "push"]
            if msg:
                cmd += ["-m", msg]
            run_command_live(cmd)
        elif choice == '2':
            run_command_live(["git", "stash", "pop"])
        elif choice == '3':
            run_command_live(["git", "stash", "apply"])
        elif choice == '4':
            run_command_live(["git", "stash", "drop"])
        elif choice == '5':
            ans = input(f"{BOLD}{RED}⚠️ 警告：確定要刪除所有的 Stash 暫存記錄嗎？這無法復原！(y/N): {RESET}").strip().lower()
            if ans == 'y':
                run_command_live(["git", "stash", "clear"])
        elif choice == '6' or not choice:
            break
            
        input(f"\n{GRAY}請按 Enter 鍵繼續...{RESET}")

def tag_management_flow(config):
    while True:
        print(CLEAR_SCREEN)
        print(f"{BOLD}{BLUE}=== 🏷️ Tag 版本標籤管理 ==={RESET}\n")
        
        res_list = subprocess.run(["git", "tag", "-n1"], capture_output=True, text=True)
        tag_output = res_list.stdout.strip()
        if tag_output:
            print(f"{BOLD}{YELLOW}目前的 Tag 標籤清單：{RESET}")
            print(f"{CYAN}{tag_output}{RESET}\n")
        else:
            print(f"{GRAY}(目前尚無任何 Tag 標籤){RESET}\n")
            
        print("1. ➕ 建立新 Tag (Create Tag)")
        print("2. 🗑️ 刪除本地 Tag (Delete Tag)")
        print("3. 🚀 推送所有 Tag 到遠端倉庫 (Push Tags)")
        print("4. ⬅️ 返回主選單")
        
        choice = input("\n請選擇操作 (1-4): ").strip()
        if choice == '1':
            tag_name = input("請輸入 Tag 名稱 (例如 v1.0.0): ").strip()
            if not tag_name:
                continue
            msg = input("請輸入 Tag 備註訊息 (選填): ").strip()
            cmd = ["git", "tag"]
            if msg:
                cmd += ["-a", tag_name, "-m", msg]
            else:
                cmd.append(tag_name)
            rc = run_command_live(cmd)
            if rc == 0:
                print(f"{GREEN}✔ 成功建立 Tag: {tag_name}{RESET}")
        elif choice == '2':
            tag_name = input("請輸入要刪除的 Tag 名稱: ").strip()
            if not tag_name:
                continue
            rc = run_command_live(["git", "tag", "-d", tag_name])
            if rc == 0:
                print(f"{GREEN}✔ 成功刪除 Tag: {tag_name}{RESET}")
        elif choice == '3':
            git_info = get_git_info()
            if git_info["remote_url"] == "None":
                print(f"{RED}錯誤：尚未綁定遠端倉庫，無法推送。{RESET}")
            else:
                run_push_with_fallback(config, ["git", "push", "origin", "--tags"])
        elif choice == '4' or not choice:
            break
            
        input(f"\n{GRAY}請按 Enter 鍵繼續...{RESET}")

# --- Main Entry ---

def main():
    if not shutil.which("git"):
        print(f"{RED}錯誤: 本系統未安裝 git CLI，請先安裝 git。{RESET}")
        sys.exit(1)
        
    config = load_config()
    ensure_gitignore()
    
    # Check if there is an active provider login on startup and set default if needed
    if config["github_token"]:
        config["active_provider"] = "github"
    elif config["gitlab_token"]:
        config["active_provider"] = "gitlab"
        
    menu_options = [
        {"name": "帳號與授權", "is_header": True},
        {"name": "🔑 平台登入與授權管理 (GitHub / GitLab)", "func": lambda: login_flow(config)},
        
        {"name": "本地倉庫管理", "is_header": True},
        {"name": "📁 初始化本地 Git 倉庫 (git init)", "func": init_flow},
        {"name": "📥 克隆/下載遠端倉庫 (git clone)", "func": lambda: clone_flow(config)},
        {"name": "🗑️ 刪除專案內檔案 (安全移除/git rm)", "func": delete_files_flow},
        
        {"name": "日常提交與推送", "is_header": True},
        {"name": "📤 一鍵暫存、提交並 Push 推送", "func": lambda: push_flow(config)},
        {"name": "🔄 檢查更新並 Pull 推送 (適合已有變更的倉庫)", "func": lambda: quick_push_existing_flow(config)},
        {"name": "🔍 暫存區與檔案差異管理 (Staging & Diff)", "func": interactive_staging_flow},
        {"name": "📦 Stash 暫存進度管理 (Git Stash)", "func": stash_management_flow},
        {"name": "🔗 變更/設定遠端倉庫網址 (git remote url)", "func": change_remote_flow},
        
        {"name": "專案與分支管理", "is_header": True},
        {"name": "🌿 本地分支管理 (切換/建立/刪除/合併)", "func": branch_management_flow},
        {"name": "🌿 圖形化分支樹狀圖 (Commit Graph)", "func": commit_graph_flow},
        {"name": "🏷️ Tag 版本標籤管理 (Git Tags)", "func": lambda: tag_management_flow(config)},
        {"name": "📜 查看最近提交歷史 (git log)", "func": commit_history_flow},
        {"name": "📋 查看雲端 Open Issues (最近 15 筆)", "func": lambda: view_issues_flow(config)},
        
        {"name": "快速一鍵發布", "is_header": True},
        {"name": "🆕 在雲端創建全新空白倉庫", "func": lambda: create_repo_flow(config)},
        {"name": "⚡ 建立全新雲端倉庫並推送此目錄所有檔案", "func": lambda: quick_create_push_flow(config)},
        {"name": "⚡ 指定現有雲端倉庫並推送此目錄所有檔案", "func": lambda: quick_specify_push_flow(config)},
        
        {"name": "團隊協作", "is_header": True},
        {"name": "👥 新增倉庫協作者 (Add Collaborator)", "func": lambda: add_collaborator_flow(config)},
        {"name": "👥 查看專案協作者清單 (Collaborators)", "func": lambda: view_collaborators_flow(config)},
        {"name": "🔀 建立 Pull Request / Merge Request (PR / MR)", "func": lambda: create_pr_flow(config)},
        
        {"name": "系統操作", "is_header": True},
        {"name": "❌ 結束並退出程式", "func": None}
    ]
    
    try:
        while True:
            sel = run_menu(menu_options, config, "主選單")
            if sel is None or sel == len(menu_options) - 1:
                print(f"\n感謝使用 GTUI，再見！")
                break
                
            # Run selected action in cooked mode
            print(CLEAR_SCREEN)
            action_func = menu_options[sel].get("func")
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
