#!/bin/bash

# Beautiful Console UI Library for Kubernetes Monitoring
# Colors and formatting functions

# Color definitions
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
BOLD='\033[1m'
UNDERLINE='\033[4m'
NC='\033[0m' # No Color

# Background colors
BG_RED='\033[41m'
BG_GREEN='\033[42m'
BG_YELLOW='\033[43m'
BG_BLUE='\033[44m'
BG_PURPLE='\033[45m'
BG_CYAN='\033[46m'

# Emoji and symbols
CHECK="✅"
CROSS="❌"
WARNING="⚠️"
INFO="ℹ️"
ROCKET="🚀"
GEAR="⚙️"
CHART="📊"
GLOBE="🌐"
HOUSE="🏠"
BOX="📦"
REFRESH="🔄"
DISK="💾"
HEALTH="🩺"
CLOCK="🕐"
FIRE="🔥"
STAR="⭐"
DIAMOND="💎"
LIGHTNING="⚡"

# Beautiful header function
print_header() {
    local title="$1"
    local width=80
    local padding=$(( (width - ${#title} - 4) / 2 ))
    
    printf "${BOLD}${CYAN}"
    printf '%*s' "$width" '' | tr ' ' '='
    printf "\n"
    printf "%*s${BOLD}${WHITE} $title ${CYAN}%*s\n" "$padding" "" "$padding" ""
    printf '%*s' "$width" '' | tr ' ' '='
    printf "${NC}\n"
    printf "\n"
}

# Section header function
print_section() {
    local icon="$1"
    local title="$2"
    printf "${BOLD}${BLUE}$icon $title${NC}\n"
    printf "${BLUE}$(printf '%*s' ${#title} '' | tr ' ' '-')${NC}\n"
}

# Status indicators
status_healthy() {
    printf "${GREEN}${CHECK} $1${NC}\n"
}

status_unhealthy() {
    printf "${RED}${CROSS} $1${NC}\n"
}

status_warning() {
    printf "${YELLOW}${WARNING} $1${NC}\n"
}

status_info() {
    printf "${CYAN}${INFO} $1${NC}\n"
}

# Progress bar function
progress_bar() {
    local current=$1
    local total=$2
    local width=50
    local percentage=$((current * 100 / total))
    local filled=$((current * width / total))
    local empty=$((width - filled))
    
    printf "${GREEN}["
    printf '%*s' "$filled" '' | tr ' ' '█'
    printf '%*s' "$empty" '' | tr ' ' '░'
    printf "] ${WHITE}${percentage}%%${NC}"
}

# Box drawing function
draw_box() {
    local content="$1"
    local width=${2:-60}
    local padding=2
    
    # Top border
    printf "${CYAN}┌$(printf '%*s' $((width-2)) '' | tr ' ' '─')┐${NC}\n"
    
    # Content with padding
    while IFS= read -r line; do
        local content_length=${#line}
        local spaces=$((width - content_length - 2*padding - 2))
        printf "${CYAN}│${NC}%*s${WHITE}%s${NC}%*s${CYAN}│${NC}\n" "$padding" "" "$line" "$spaces" ""
    done <<< "$content"
    
    # Bottom border
    printf "${CYAN}└$(printf '%*s' $((width-2)) '' | tr ' ' '─')┘${NC}\n"
}

# Table header function with dynamic width calculation
table_header() {
    local headers=("$@")
    
    # Initialize column widths with header lengths
    COLUMN_WIDTHS=()
    for header in "${headers[@]}"; do
        COLUMN_WIDTHS+=(${#header})
    done
    
    # Export for use in table_row function
    export COLUMN_COUNT=${#headers[@]}
}

# Function to update column widths based on content
update_column_widths() {
    local cells=("$@")
    
    for ((i=0; i<${#cells[@]} && i<COLUMN_COUNT; i++)); do
        local cell_length=${#cells[i]}
        if [ $cell_length -gt ${COLUMN_WIDTHS[i]} ]; then
            COLUMN_WIDTHS[i]=$cell_length
        fi
    done
}

# Function to print table border
print_table_border() {
    local border_type="$1"  # top, middle, bottom
    
    case $border_type in
        "top")
            printf "${BOLD}${WHITE}┌"
            for ((i=0; i<COLUMN_COUNT; i++)); do
                printf '%*s' $((${COLUMN_WIDTHS[i]} + 2)) '' | tr ' ' '─'
                if [ $i -lt $((COLUMN_COUNT - 1)) ]; then
                    printf "┬"
                fi
            done
            printf "┐\n${NC}"
            ;;
        "middle")
            printf "${WHITE}├"
            for ((i=0; i<COLUMN_COUNT; i++)); do
                printf '%*s' $((${COLUMN_WIDTHS[i]} + 2)) '' | tr ' ' '─'
                if [ $i -lt $((COLUMN_COUNT - 1)) ]; then
                    printf "┼"
                fi
            done
            printf "┤\n${NC}"
            ;;
        "bottom")
            printf "${WHITE}└"
            for ((i=0; i<COLUMN_COUNT; i++)); do
                printf '%*s' $((${COLUMN_WIDTHS[i]} + 2)) '' | tr ' ' '─'
                if [ $i -lt $((COLUMN_COUNT - 1)) ]; then
                    printf "┴"
                fi
            done
            printf "┘\n${NC}"
            ;;
    esac
}

# Updated table_row function
table_row() {
    local cells=("$@")
    local colors=("${WHITE}" "${GREEN}" "${CYAN}" "${YELLOW}" "${PURPLE}")
    
    # Update column widths if this is content (not header)
    if [ "$1" != "__HEADER__" ]; then
        update_column_widths "$@"
    fi
    
    printf "${WHITE}│"
    for ((i=0; i<COLUMN_COUNT; i++)); do
        local color=${colors[$((i % ${#colors[@]}))]}
        local cell_content="${cells[i]:-}"
        local width=${COLUMN_WIDTHS[i]}
        
        if [ "$1" = "__HEADER__" ]; then
            # Header formatting
            printf " ${BOLD}${YELLOW}%-${width}s${WHITE} │" "$cell_content"
        else
            # Regular row formatting
            printf " ${color}%-${width}s${WHITE} │" "$cell_content"
        fi
    done
    printf "${NC}\n"
}

# New function to render complete table
render_table() {
    local headers=("$@")
    
    # First pass: collect all data and calculate max widths
    print_table_border "top"
    
    # Print header row
    table_row "__HEADER__" "${headers[@]}"
    
    print_table_border "middle"
}

# Table footer function
table_footer() {
    print_table_border "bottom"
}

# Animated loading function
loading_animation() {
    local pid=$1
    local message="$2"
    local frames=("⠋" "⠙" "⠹" "⠸" "⠼" "⠴" "⠦" "⠧" "⠇" "⠏")
    local i=0
    
    while kill -0 $pid 2>/dev/null; do
        printf "\r${CYAN}${frames[i]} ${WHITE}$message${NC}"
        i=$(( (i + 1) % ${#frames[@]} ))
        sleep 0.1
    done
    printf "\r${GREEN}${CHECK} $message complete!${NC}\n"
}

# Export functions for use in other scripts
export -f print_header print_section status_healthy status_unhealthy status_warning status_info
export -f progress_bar draw_box table_header table_row table_footer loading_animation
export -f update_column_widths print_table_border render_table 