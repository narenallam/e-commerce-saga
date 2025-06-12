#!/bin/bash

# Demo script for Beautiful Kubernetes Console Interface
source scripts/console-ui.sh

clear
print_header "🎨 BEAUTIFUL KUBERNETES CONSOLE INTERFACE DEMO"

echo
status_info "Welcome to the enhanced Kubernetes monitoring system!"
echo

print_section "🌟" "AVAILABLE COMMANDS"
echo
printf "  \033[1;33m1.\033[0m \033[0;36mmake help\033[0m        - Beautiful help interface\n"
printf "  \033[1;33m2.\033[0m \033[0;32mmake health\033[0m      - Complete cluster health dashboard\n"
printf "  \033[1;33m3.\033[0m \033[0;35mmake cluster-info\033[0m - Detailed cluster topology\n"
printf "  \033[1;33m4.\033[0m \033[0;31mmake monitor\033[0m     - Real-time monitoring (live updates)\n"
printf "  \033[1;33m5.\033[0m \033[0;34mmake metrics\033[0m     - Install metrics server\n"
echo

print_section "✨" "BEAUTIFUL FEATURES"
echo
status_healthy "Color-coded status indicators (🟢 Running, 🟡 Pending, 🔴 Failed)"
status_healthy "Visual progress bars and charts"
status_healthy "Master/Worker node identification (👑 vs 🔧)"
status_healthy "Pod placement visualization with dots (●●●)"
status_healthy "Priority-based service classification (🔥 High, ⚡ Medium, 💎 Low)"
status_healthy "Real-time endpoint monitoring (🌟 Connected, 💥 Disconnected)"
status_healthy "Professional table formatting with borders"
echo

print_section "🚀" "SYSTEM STATUS"
echo
running_pods=$(kubectl get pods -n e-commerce-saga --no-headers 2>/dev/null | grep "Running" | wc -l | tr -d ' ')
total_pods=$(kubectl get pods -n e-commerce-saga --no-headers 2>/dev/null | wc -l | tr -d ' ')

if [ "$total_pods" -gt 0 ]; then
    printf "\033[0;32m🚀 Cluster Status: $running_pods/$total_pods pods running\033[0m "
    for ((i=1; i<=running_pods; i++)); do printf "\033[0;32m●\033[0m"; done
    for ((i=running_pods+1; i<=total_pods; i++)); do printf "\033[0;31m●\033[0m"; done
    echo
    echo
    status_healthy "All systems operational! 🎯"
else
    status_warning "No pods found - run 'make deploy' first"
fi

echo
print_section "💡" "QUICK START"
echo
printf "\033[0;36m   make health\033[0m      # See cluster overview\n"
printf "\033[0;36m   make cluster-info\033[0m # Detailed topology\n"
printf "\033[0;36m   make monitor\033[0m     # Live monitoring\n"
echo

draw_box "🎨 Your Kubernetes cluster now has a beautiful console interface! 
Enjoy monitoring with style and colors! ✨"

echo 