#!/usr/bin/env bash

# GTUI Installer Script
# Works on macOS and Linux (Unix-based devices)

set -e

# Setup colors
BLUE="\033[38;5;75m"
GREEN="\033[38;5;120m"
YELLOW="\033[38;5;220m"
RED="\033[38;5;203m"
RESET="\033[0m"

echo -e "${BLUE}⚡ 正在安裝 GTUI (極簡終端 Git 控制台)...${RESET}"

# Check python3
if ! command -v python3 &>/dev/null; then
    echo -e "${RED}❌ 錯誤: 本系統未檢測到 Python 3，請先安裝 Python 3。${RESET}"
    exit 1
fi

# Check git
if ! command -v git &>/dev/null; then
    echo -e "${YELLOW}⚠️  警告: 本系統未檢測到 git CLI，請記得在安裝後安裝 git。${RESET}"
fi

# Define binary name and path
INSTALL_DIR="$HOME/.local/bin"
TARGET_BIN="$INSTALL_DIR/gtui"

# Create directories if they don't exist
mkdir -p "$INSTALL_DIR"

# Copy python script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/gtui.py" ]; then
    cp "$SCRIPT_DIR/gtui.py" "$TARGET_BIN"
else
    # Fallback to current directory check
    if [ -f "./gtui.py" ]; then
        cp "./gtui.py" "$TARGET_BIN"
    else
        echo -e "${RED}❌ 錯誤: 找不到 gtui.py 原始檔！請在 gtui.py 所在的目錄下執行此腳本。${RESET}"
        exit 1
    fi
fi

# Make it executable
chmod +x "$TARGET_BIN"

# Check if path is in PATH
PATH_EXISTS=false
if [[ ":$PATH:" == *":$INSTALL_DIR:"* ]]; then
    PATH_EXISTS=true
fi

SHELL_CONFIG=""
DETECTED_SHELL="$(basename "$SHELL")"

if [ "$DETECTED_SHELL" = "zsh" ]; then
    SHELL_CONFIG="$HOME/.zshrc"
elif [ "$DETECTED_SHELL" = "bash" ]; then
    if [ -f "$HOME/.bash_profile" ]; then
        SHELL_CONFIG="$HOME/.bash_profile"
    elif [ -f "$HOME/.bashrc" ]; then
        SHELL_CONFIG="$HOME/.bashrc"
    else
        SHELL_CONFIG="$HOME/.profile"
    fi
else
    SHELL_CONFIG="$HOME/.profile"
fi

if [ "$PATH_EXISTS" = false ]; then
    echo -e "${YELLOW}正在將 $INSTALL_DIR 新增到您的 PATH 系統變數中...${RESET}"
    
    # Create the config file if it doesn't exist
    touch "$SHELL_CONFIG"
    
    # Append path export
    echo "" >> "$SHELL_CONFIG"
    echo "# GTUI executable path" >> "$SHELL_CONFIG"
    echo "export PATH=\"\$PATH:$INSTALL_DIR\"" >> "$SHELL_CONFIG"
    
    echo -e "${GREEN}✔ 成功在 $SHELL_CONFIG 新增 PATH 設定！${RESET}"
    echo -e "${YELLOW}請執行 'source $SHELL_CONFIG' 或重啟終端機以套用設定。${RESET}"
else
    echo -e "${GREEN}✔ $INSTALL_DIR 已經在 PATH 系統變數中。${RESET}"
fi

echo -e "\n${GREEN}🎉 GTUI 安裝完成！${RESET}"
echo -e "您可以直接在終端機輸入 ${BLUE}gtui${RESET} 即可啟動極簡 TUI Git 頁面。"
echo -e "如果無法直接執行，請重新載入設定檔: ${BLUE}source $SHELL_CONFIG${RESET}\n"
