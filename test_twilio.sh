#!/bin/bash
# Twilio Test Script - Test SMS and WhatsApp functionality

set -e

echo "🧪 Mecris Twilio Test Suite"
echo "=========================="
echo

# Check if virtual environment is activated
if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
fi

# Function to check environment variables
check_env_vars() {
    echo "📋 Checking environment variables..."
    
    missing_vars=()
    
    if [ -z "$TWILIO_ACCOUNT_SID" ]; then
        missing_vars+=("TWILIO_ACCOUNT_SID")
    fi
    
    if [ -z "$TWILIO_AUTH_TOKEN" ]; then
        missing_vars+=("TWILIO_AUTH_TOKEN")
    fi
    
    if [ -z "$TWILIO_FROM_NUMBER" ]; then
        missing_vars+=("TWILIO_FROM_NUMBER")
    fi
    
    if [ -z "$TWILIO_TO_NUMBER" ]; then
        missing_vars+=("TWILIO_TO_NUMBER")
    fi
    
    if [ ${#missing_vars[@]} -gt 0 ]; then
        echo "❌ Missing required environment variables:"
        printf '   - %s\n' "${missing_vars[@]}"
        echo
        echo "Please set these in your .env file or environment:"
        echo "   TWILIO_ACCOUNT_SID=your_account_sid"
        echo "   TWILIO_AUTH_TOKEN=your_auth_token"
        echo "   TWILIO_FROM_NUMBER=+1234567890"
        echo "   TWILIO_TO_NUMBER=+1234567890"
        echo "   TWILIO_WHATSAPP_FROM=whatsapp:+14155238886  # Optional, uses sandbox default"
        exit 1
    else
        echo "✅ All required environment variables are set"
        echo "   Account SID: ${TWILIO_ACCOUNT_SID:0:8}..."
        echo "   From Number: $TWILIO_FROM_NUMBER"
        echo "   To Number: $TWILIO_TO_NUMBER"
        echo
    fi
}

# Function to test SMS functionality
test_sms() {
    echo "📱 Testing SMS functionality..."
    
    message="🧠 Mecris SMS Test - $(date +'%H:%M:%S')"
    
    echo "Sending test SMS: '$message'"
    
    if python3 -c "
import sys
sys.path.append('.')
from twilio_sender import send_sms
success = send_sms('$message')
exit(0 if success else 1)
"; then
        echo "✅ SMS sent successfully!"
    else
        echo "❌ SMS failed to send"
        return 1
    fi
    
    echo
}

# Function to test WhatsApp functionality
test_whatsapp() {
    echo "💬 Testing WhatsApp functionality..."
    
    message="🧠 Mecris WhatsApp Test - $(date +'%H:%M:%S')"
    
    echo "Sending test WhatsApp message: '$message'"
    echo "Note: WhatsApp requires sandbox setup if using default number"
    
    if python3 -c "
import sys
sys.path.append('.')
from twilio_sender import send_message
success = send_message('$message')
exit(0 if success else 1)
"; then
        echo "✅ WhatsApp message sent successfully!"
    else
        echo "❌ WhatsApp message failed to send"
        echo "   This may be normal if WhatsApp sandbox isn't set up"
        return 1
    fi
    
    echo
}

# Function to test budget alert
test_budget_alert() {
    echo "🚨 Testing budget alert functionality..."
    
    echo "Sending test budget alert (simulating low credits)..."
    
    if python3 -c "
import sys
sys.path.append('.')
from twilio_sender import budget_alert
budget_alert(2.50, 1.25)  # Simulates 2 days left
print('Budget alert triggered')
"; then
        echo "✅ Budget alert sent successfully!"
    else
        echo "❌ Budget alert failed to send"
        return 1
    fi
    
    echo
}

# Function to test MCP server integration
test_mcp_integration() {
    echo "🔌 Testing MCP server integration..."
    
    # Check if server is running
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo "✅ MCP server is running"
        
        echo "Testing beeminder alert endpoint..."
        if curl -s -X POST http://localhost:8000/beeminder/alert | grep -q "alert_sent"; then
            echo "✅ Beeminder alert endpoint works"
        else
            echo "⚠️  Beeminder alert endpoint may not be configured"
        fi
        
        echo "Testing usage alert endpoint..."
        if curl -s -X POST http://localhost:8000/usage/alert | grep -q "alert_sent"; then
            echo "✅ Usage alert endpoint works"
        else
            echo "⚠️  Usage alert endpoint may not be configured"
        fi
        
    else
        echo "⚠️  MCP server is not running - start with ./scripts/launch_server.sh"
        return 1
    fi
    
    echo
}

# Function to run interactive test
interactive_test() {
    echo "🎛️  Interactive Test Mode"
    echo
    
    while true; do
        echo "Choose a test to run:"
        echo "  1) Send SMS"
        echo "  2) Send WhatsApp message"
        echo "  3) Send budget alert"
        echo "  4) Custom message (SMS)"
        echo "  5) Custom message (WhatsApp)"
        echo "  6) Exit"
        echo
        
        read -p "Enter choice (1-6): " choice
        
        case $choice in
            1)
                echo
                test_sms
                ;;
            2)
                echo
                test_whatsapp
                ;;
            3)
                echo
                test_budget_alert
                ;;
            4)
                echo
                read -p "Enter custom SMS message: " custom_msg
                if [ -n "$custom_msg" ]; then
                    python3 -c "
import sys
sys.path.append('.')
from twilio_sender import send_sms
success = send_sms('$custom_msg')
print('✅ SMS sent!' if success else '❌ SMS failed')
"
                fi
                echo
                ;;
            5)
                echo
                read -p "Enter custom WhatsApp message: " custom_msg
                if [ -n "$custom_msg" ]; then
                    python3 -c "
import sys
sys.path.append('.')
from twilio_sender import send_message
success = send_message('$custom_msg')
print('✅ WhatsApp sent!' if success else '❌ WhatsApp failed')
"
                fi
                echo
                ;;
            6)
                echo "👋 Goodbye!"
                exit 0
                ;;
            *)
                echo "Invalid choice, please try again"
                echo
                ;;
        esac
    done
}

# Main test runner
main() {
    check_env_vars
    
    if [ "$1" == "interactive" ] || [ "$1" == "-i" ]; then
        interactive_test
        return
    fi
    
    echo "🚀 Running all tests..."
    echo
    
    # Track test results
    passed=0
    total=0
    
    # Run tests
    if test_sms; then ((passed++)); fi
    ((total++))
    
    if test_whatsapp; then ((passed++)); fi
    ((total++))
    
    if test_budget_alert; then ((passed++)); fi
    ((total++))
    
    if test_mcp_integration; then ((passed++)); fi
    ((total++))
    
    # Summary
    echo "📊 Test Results:"
    echo "   Passed: $passed/$total"
    
    if [ $passed -eq $total ]; then
        echo "🎉 All tests passed!"
        exit 0
    else
        echo "⚠️  Some tests failed - check configuration"
        exit 1
    fi
}

# Show usage if requested
if [ "$1" == "--help" ] || [ "$1" == "-h" ]; then
    echo "Usage: $0 [interactive|--help]"
    echo
    echo "Options:"
    echo "  interactive, -i    Run in interactive mode"
    echo "  --help, -h        Show this help"
    echo
    echo "Environment variables required:"
    echo "  TWILIO_ACCOUNT_SID     Your Twilio Account SID"
    echo "  TWILIO_AUTH_TOKEN      Your Twilio Auth Token"
    echo "  TWILIO_FROM_NUMBER     Your Twilio phone number (+1234567890)"
    echo "  TWILIO_TO_NUMBER       Your destination phone number (+1234567890)"
    echo
    echo "Optional:"
    echo "  TWILIO_WHATSAPP_FROM   WhatsApp sender (defaults to sandbox)"
    echo
    exit 0
fi

# Run main function
main "$@"