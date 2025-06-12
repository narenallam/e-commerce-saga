#!/bin/bash

# Health monitoring script using console UI functions
source scripts/console-ui.sh

# Function to render a complete table with proper column sizing
render_complete_table() {
    local temp_file="$1"
    shift
    local headers=("$@")
    
    # Initialize table with headers
    table_header "${headers[@]}"
    
    # First pass: read all data to calculate column widths including headers
    for ((i=0; i<${#headers[@]}; i++)); do
        local header_length=${#headers[i]}
        if [ $header_length -gt ${COLUMN_WIDTHS[i]} ]; then
            COLUMN_WIDTHS[i]=$header_length
        fi
    done
    
    while IFS=$'\t' read -r -a row_data; do
        for ((i=0; i<${#row_data[@]} && i<${#headers[@]}; i++)); do
            local cell_length=${#row_data[i]}
            if [ $cell_length -gt ${COLUMN_WIDTHS[i]} ]; then
                COLUMN_WIDTHS[i]=$cell_length
            fi
        done
    done < "$temp_file"
    
    # Now render the table with proper widths
    print_table_border "top"
    
    # Render header row
    printf "${WHITE}│"
    for ((i=0; i<${#headers[@]}; i++)); do
        local width=${COLUMN_WIDTHS[i]}
        printf " ${BOLD}${YELLOW}%-${width}s${WHITE} │" "${headers[i]}"
    done
    printf "${NC}\n"
    
    print_table_border "middle"
    
    # Render all data rows
    while IFS=$'\t' read -r -a row_data; do
        printf "${WHITE}│"
        for ((i=0; i<${#headers[@]}; i++)); do
            local width=${COLUMN_WIDTHS[i]}
            local color
            case $i in
                0) color="${GREEN}" ;;
                1) color="${CYAN}" ;;
                2) color="${YELLOW}" ;;
                3) color="${PURPLE}" ;;
                *) color="${WHITE}" ;;
            esac
            printf " ${color}%-${width}s${WHITE} │" "${row_data[i]:-}"
        done
        printf "${NC}\n"
    done < "$temp_file"
    
    table_footer
}

health_check() {
    clear
    print_header "🩺 SERVICE HEALTH & APPLICATION STATUS"
    
    printf "\033[1;37m\033[4m📊 APPLICATION OVERVIEW\033[0m\n"
    echo
    
    running_pods=$(kubectl get pods -n e-commerce-saga --no-headers 2>/dev/null | grep "Running" | wc -l | tr -d ' ')
    total_pods=$(kubectl get pods -n e-commerce-saga --no-headers 2>/dev/null | wc -l | tr -d ' ')
    
    if [ "$total_pods" -gt 0 ]; then
        printf "\033[0;32m🚀 Application Status: $running_pods/$total_pods services running\033[0m "
        for ((i=1; i<=running_pods; i++)); do printf "\033[0;32m●\033[0m"; done
        for ((i=running_pods+1; i<=total_pods; i++)); do printf "\033[0;31m●\033[0m"; done
        printf "\n"
    else
        status_warning "No services deployed - run 'make deploy' first"
    fi
    
    printf "\n"
    print_section "🔄" "SERVICE DEPLOYMENT STATUS"
    
    # Service deployment table
    temp_file=$(mktemp)
    kubectl get deployments -n e-commerce-saga -o custom-columns="NAME:.metadata.name,DESIRED:.spec.replicas,CURRENT:.status.replicas,READY:.status.readyReplicas" --no-headers 2>/dev/null | while read name desired current ready; do
        if [ "$ready" = "$desired" ]; then
            health_status="✅ Healthy"
        else
            health_status="⚠️  Scaling"
        fi
        printf "%s\t%s\t%s\t%s\t%s\n" "$name" "$desired" "$current" "$ready" "$health_status"
    done > "$temp_file"
    
    render_complete_table "$temp_file" "SERVICE" "DESIRED" "CURRENT" "READY" "HEALTH"
    rm -f "$temp_file"
    
    printf "\n"
    print_section "📦" "CONTAINER STATUS"
    
    # Container status table
    temp_file=$(mktemp)
    kubectl get pods -n e-commerce-saga -o custom-columns="NAME:.metadata.name,STATUS:.status.phase,RESTARTS:.status.containerStatuses[0].restartCount,AGE:.status.startTime" --no-headers 2>/dev/null | while read name status restarts start_time; do
        age_formatted=$(echo $start_time | awk -F'T' '{print $1}' | awk -F'-' '{print $2"/"$3}')
        
        if [ "$status" = "Running" ]; then
            status_formatted="🟢 Running $name"
        elif [ "$status" = "Pending" ]; then
            status_formatted="🟡 Pending $name"
        else
            status_formatted="🔴 Error $name"
        fi
        
        printf "%s\t%s\t%s\t%s\n" "$status_formatted" "$status" "$restarts" "$age_formatted"
    done > "$temp_file"
    
    render_complete_table "$temp_file" "POD NAME" "STATUS" "RESTARTS" "UPTIME"
    rm -f "$temp_file"
    
    printf "\n"
    print_section "🌐" "SERVICE CONNECTIVITY"
    
    # Service connectivity table
    temp_file=$(mktemp)
    kubectl get svc -n e-commerce-saga --no-headers 2>/dev/null | while read name type cluster_ip external_ip port age; do
        port_clean=$(echo $port | cut -d'/' -f1)
        endpoints=$(kubectl get endpoints $name -n e-commerce-saga -o jsonpath='{.subsets[0].addresses[*].ip}' 2>/dev/null | wc -w | tr -d ' ')
        
        if [ "$endpoints" -gt 0 ]; then
            service_formatted="🌟 $name"
            status_formatted="Connected"
            endpoints_formatted="$endpoints ready"
        else
            service_formatted="💥 $name"
            status_formatted="Disconnected"
            endpoints_formatted="no endpoints"
        fi
        
        printf "%s\t%s\t%s\t%s\n" "$service_formatted" "$port_clean" "$endpoints_formatted" "$status_formatted"
    done > "$temp_file"
    
    render_complete_table "$temp_file" "SERVICE" "PORT" "ENDPOINTS" "STATUS"
    rm -f "$temp_file"
    
    printf "\n"
    print_section "🩺" "APPLICATION HEALTH CHECKS"
    
    if pgrep -f "kubectl port-forward.*e-commerce-saga" > /dev/null; then
        status_healthy "Port forwarding is active - performing health checks..."
        printf "\n"
        PYTHONPATH=src python3 scripts/monitoring/check_health.py 2>/dev/null || status_warning "Health check script failed"
    else
        status_warning "Port forwarding not active - cannot perform application health checks"
        status_info "Run 'make port-forward' to enable detailed health checking"
        printf "\n"
        
        # Basic service health table
        temp_file=$(mktemp)
        services=("order-service" "inventory-service" "payment-service" "shipping-service" "notification-service" "saga-coordinator")
        for service in "${services[@]}"; do
            printf "%s\t%s\t%s\n" "$service" "Unknown" "Need port-forward"
        done > "$temp_file"
        
        render_complete_table "$temp_file" "SERVICE" "STATUS" "NOTE"
        rm -f "$temp_file"
    fi
}

# Run the health check
health_check 