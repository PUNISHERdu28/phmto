#!/bin/bash

# =====================================
# GOD HAND BERSERK - Launcher (Bash)
# =====================================

# Parse arguments
SKIP_DEPS=false
FEMTO_ONLY=false
VOID_ONLY=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-deps)
            SKIP_DEPS=true
            shift
            ;;
        --femto-only)
            FEMTO_ONLY=true
            shift
            ;;
        --void-only)
            VOID_ONLY=true
            shift
            ;;
        *)
            echo "Usage: $0 [--skip-deps] [--femto-only] [--void-only]"
            exit 1
            ;;
    esac
done

# Configuration
FEMTO_PORT=8000
VOID_PORT=5000
PROJECT_NAME="God Hand Berserk"
PYTHON_MIN_VERSION="3.8"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Function to write colored messages
write_godhand_message() {
    local message="$1"
    local color="$2"
    local symbol="${3:-[*]}"
    
    case $color in
        "red") echo -e "${RED}${symbol} ${message}${NC}" ;;
        "green") echo -e "${GREEN}${symbol} ${message}${NC}" ;;
        "yellow") echo -e "${YELLOW}${symbol} ${message}${NC}" ;;
        "magenta") echo -e "${MAGENTA}${symbol} ${message}${NC}" ;;
        "cyan") echo -e "${CYAN}${symbol} ${message}${NC}" ;;
        *) echo "${symbol} ${message}" ;;
    esac
}

# Function to test Python installation
test_python_installation() {
    write_godhand_message "Verification de Python..." "cyan" "[CHECK]"
    
    if command -v python3 &> /dev/null; then
        PYTHON_CMD="python3"
    elif command -v python &> /dev/null; then
        PYTHON_CMD="python"
    else
        write_godhand_message "Python non trouve!" "red" "[ERROR]"
        write_godhand_message "Installez Python depuis: https://python.org" "yellow" "[INFO]"
        return 1
    fi
    
    # Get Python version
    version=$($PYTHON_CMD --version 2>&1 | grep -oE '[0-9]+\.[0-9]+')
    
    if [[ $(echo "$version >= $PYTHON_MIN_VERSION" | bc -l) -eq 1 ]]; then
        write_godhand_message "Python $version detecte [OK]" "green" "[PYTHON]"
        return 0
    else
        write_godhand_message "Python $version trop ancien (min: $PYTHON_MIN_VERSION)" "red" "[ERROR]"
        return 1
    fi
}

# Function to test port availability
test_port_availability() {
    local port=$1
    
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        return 1  # Port is occupied
    else
        return 0  # Port is available
    fi
}

# Function to install dependencies
install_dependencies() {
    write_godhand_message "Installation des dependances..." "magenta" "[INSTALL]"
    
    $PYTHON_CMD -m pip install --upgrade pip
    
    if [[ -f "requirements.txt" ]]; then
        write_godhand_message "Installation depuis requirements.txt" "cyan" "[DEPS]"
        $PYTHON_CMD -m pip install -r requirements.txt
    else
        write_godhand_message "Aucun requirements.txt trouve - dependances de base" "yellow" "[WARN]"
        local god_hand_deps=(
            "streamlit"
            "flask"
            "pandas"
            "numpy"
            "plotly"
        )
        
        for dep in "${god_hand_deps[@]}"; do
            write_godhand_message "Installation: $dep" "cyan" "[DEPS]"
            $PYTHON_CMD -m pip install "$dep" --quiet
        done
    fi
    
    write_godhand_message "Dependances installees!" "green" "[OK]"
}

# Function to start FEMTO
start_femto() {
    write_godhand_message "FEMTO - The Fallen Angel s'eveille..." "red" "[FEMTO]"
    
    if ! test_port_availability $FEMTO_PORT; then
        write_godhand_message "Port $FEMTO_PORT occupe!" "red" "[ERROR]"
        return 1
    fi
    
    # Start FEMTO in background
    $PYTHON_CMD ubik/start_solana_api.py &
    local femto_pid=$!
    
    sleep 3
    
    # Wait a bit more and verify process is healthy
    local attempts=0
    while [[ $attempts -lt 10 ]]; do
        if kill -0 $femto_pid 2>/dev/null; then
            # Test if port is responding
            if curl -s "http://localhost:$FEMTO_PORT/docs" >/dev/null 2>&1; then
                write_godhand_message "FEMTO operationnel sur port $FEMTO_PORT" "green" "[ACTIVE]"
                write_godhand_message "Swagger UI: http://localhost:$FEMTO_PORT/docs" "cyan" "[API]"
                echo $femto_pid
                return 0
            fi
        fi
        sleep 1
        ((attempts++))
    done
    
    write_godhand_message "Echec du demarrage FEMTO!" "red" "[ERROR]"
    return 1
}

# Function to start VOID
start_void() {
    write_godhand_message "VOID - The All-Seeing s'eveille..." "magenta" "[VOID]"
    
    if ! test_port_availability $VOID_PORT; then
        write_godhand_message "Port $VOID_PORT occupe!" "red" "[ERROR]"
        return 1
    fi
    
    # Start VOID in background
    streamlit run void/main_analytics.py --server.port $VOID_PORT --server.address 0.0.0.0 &
    local void_pid=$!
    
    sleep 5
    
    # Wait a bit more and verify process is healthy
    local attempts=0
    while [[ $attempts -lt 15 ]]; do
        if kill -0 $void_pid 2>/dev/null; then
            # Test if port is responding
            if curl -s "http://localhost:$VOID_PORT" >/dev/null 2>&1; then
                write_godhand_message "VOID operationnel sur port $VOID_PORT" "green" "[ACTIVE]"
                write_godhand_message "Interface: http://localhost:$VOID_PORT" "cyan" "[WEB]"
                echo $void_pid
                return 0
            fi
        fi
        sleep 1
        ((attempts++))
    done
    
    write_godhand_message "Echec du demarrage VOID!" "red" "[ERROR]"
    return 1
}

# Function to open browsers
open_browsers() {
    write_godhand_message "Ouverture des portails..." "cyan" "[BROWSER]"
    
    if [[ "$VOID_ONLY" != "true" ]]; then
        if command -v xdg-open &> /dev/null; then
            xdg-open "http://localhost:$FEMTO_PORT/docs" &
        elif command -v open &> /dev/null; then
            open "http://localhost:$FEMTO_PORT/docs" &
        fi
    fi
    
    if [[ "$FEMTO_ONLY" != "true" ]]; then
        if command -v xdg-open &> /dev/null; then
            xdg-open "http://localhost:$VOID_PORT" &
        elif command -v open &> /dev/null; then
            open "http://localhost:$VOID_PORT" &
        fi
    fi
}

# Function to show God Hand banner
show_godhand_banner() {
    echo ""
    echo -e "${MAGENTA}==========================================${NC}"
    echo -e "${MAGENTA}        GOD HAND BERSERK LAUNCHER        ${NC}"
    echo -e "${MAGENTA}==========================================${NC}"
    echo -e "${RED}  FEMTO - The Fallen Angel              ${NC}"
    echo -e "${MAGENTA}  VOID  - The All-Seeing                ${NC}"
    echo -e "${MAGENTA}==========================================${NC}"
    echo ""
}

# Function to wait for exit
wait_for_exit() {
    local femto_pid=$1
    local void_pid=$2
    
    write_godhand_message "Systeme actif. Appuyez sur Ctrl+C pour arreter..." "green" "[RUNNING]"
    
    # Trap for clean shutdown
    trap 'cleanup_and_exit $femto_pid $void_pid' INT TERM
    
    while true; do
        sleep 1
        
        if [[ -n "$femto_pid" ]] && ! kill -0 $femto_pid 2>/dev/null; then
            write_godhand_message "FEMTO s'est arrete!" "red" "[DIED]"
        fi
        if [[ -n "$void_pid" ]] && ! kill -0 $void_pid 2>/dev/null; then
            write_godhand_message "VOID s'est arrete!" "red" "[DIED]"
        fi
    done
}

# Function to cleanup and exit
cleanup_and_exit() {
    local femto_pid=$1
    local void_pid=$2
    
    echo ""
    write_godhand_message "Arret du systeme God Hand..." "yellow" "[STOP]"
    
    if [[ -n "$femto_pid" ]] && kill -0 $femto_pid 2>/dev/null; then
        kill $femto_pid 2>/dev/null
    fi
    if [[ -n "$void_pid" ]] && kill -0 $void_pid 2>/dev/null; then
        kill $void_pid 2>/dev/null
    fi
    
    exit 0
}

# =====================================
# EXECUTION PRINCIPALE
# =====================================

show_godhand_banner

if ! test_python_installation; then
    exit 1
fi

if [[ "$SKIP_DEPS" != "true" ]]; then
    install_dependencies
fi

femto_pid=""
void_pid=""

if [[ "$VOID_ONLY" != "true" ]]; then
    femto_pid=$(start_femto)
fi

if [[ "$FEMTO_ONLY" != "true" ]]; then
    void_pid=$(start_void)
fi

sleep 2
open_browsers

echo ""
write_godhand_message "SYSTEME GOD HAND OPERATIONNEL" "green" "[SUCCESS]"
echo ""

if [[ -n "$femto_pid" ]]; then
    echo -e "${RED}FEMTO (API Solana)    : http://localhost:$FEMTO_PORT/docs${NC}"
fi
if [[ -n "$void_pid" ]]; then
    echo -e "${MAGENTA}VOID (Analytics IA)   : http://localhost:$VOID_PORT${NC}"
fi

echo ""

wait_for_exit "$femto_pid" "$void_pid"