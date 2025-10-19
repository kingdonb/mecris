# 🛠️ Development Environment Setup

This guide helps you set up the Boris & Fiona Walk Reminder development environment with direnv and make commands.

## 🚀 Quick Start

### 1. **Install Prerequisites**
```bash
# Install direnv (environment variable management)
brew install direnv  # macOS
# or: apt install direnv  # Ubuntu
# or: pacman -S direnv   # Arch

# Add direnv to your shell
echo 'eval "$(direnv hook zsh)"' >> ~/.zshrc  # for zsh
echo 'eval "$(direnv hook bash)"' >> ~/.bashrc  # for bash
source ~/.zshrc  # or restart terminal
```

### 2. **Setup Environment Variables**
```bash
# Copy the template and edit with your credentials
cp .envrc.template .envrc
nano .envrc  # or your preferred editor

# Allow direnv to load the environment
direnv allow
```

### 3. **Install Development Dependencies**
```bash
# Check and install all required tools
make install-deps
```

### 4. **Start Development**
```bash
# See all available commands
make help

# Start the server in development mode
make dev

# Or start in background for testing
make watch
make api-test
```

## 📋 Available Make Commands

Run `make help` to see all commands, but here are the most important ones:

### **Development**
- `make dev` - Start Spin app with auto-reload (recommended)
- `make watch` - Start server in background
- `make stop` - Stop all Spin processes
- `make status` - Show current system status

### **Testing**
- `make test` - Run all tests
- `make api-test` - Test the /check endpoint
- `make web-test` - Open web frontend in browser

### **Build & Deploy**
- `make build` - Build WASM component
- `make deploy` - Deploy to Spin Cloud

## 🔧 Environment Variables

The `.envrc` file contains all environment variables needed for development:

### **Required for SMS**
- `SPIN_VARIABLE_TWILIO_ACCOUNT_SID` - Your Twilio Account SID
- `SPIN_VARIABLE_TWILIO_AUTH_TOKEN` - Your Twilio Auth Token  
- `SPIN_VARIABLE_TWILIO_FROM_NUMBER` - Your Twilio phone number
- `SPIN_VARIABLE_TWILIO_TO_NUMBER` - Destination phone number

### **Optional**
- `SPIN_VARIABLE_OPENWEATHER_API_KEY` - Weather API key (future feature)
- `SPIN_LOCAL_PORT` - Development server port (default: 3000)
- `SPIN_CLOUD_APP_NAME` - Spin Cloud app name for deployment

## 🔒 Security

- ✅ `.envrc` is in `.gitignore` - never committed to git
- ✅ `.envrc.template` shows required variables without real values
- ✅ Environment variables are loaded automatically by direnv
- ✅ Make commands use environment variables, never hardcode secrets

## 🐕 Typical Development Workflow

```bash
# 1. Start development server
make dev

# 2. In another terminal, test the API
make api-test

# 3. Run tests
make test

# 4. Make changes to code (server auto-reloads)

# 5. Test changes
make api-test
make test

# 6. Stop server when done
make stop
```

## 🎯 Benefits of This Setup

### **direnv (.envrc)**
- ✅ **Automatic**: Environment variables load when you `cd` into the project
- ✅ **Secure**: Credentials never committed to git
- ✅ **Consistent**: Same environment for all developers
- ✅ **Self-documenting**: Clear variable names and descriptions

### **Makefile**
- ✅ **Simple**: Easy-to-remember commands (`make dev`, `make test`)
- ✅ **Comprehensive**: All development tasks covered
- ✅ **Self-documenting**: `make help` explains everything
- ✅ **Safe**: No hardcoded secrets, uses direnv variables

### **Combined Power**
- ✅ **One command setup**: `cp .envrc.template .envrc && direnv allow`
- ✅ **Clean development**: `make dev` just works
- ✅ **Team friendly**: New developers can start quickly
- ✅ **Production ready**: Same commands work for deployment

## 🔍 Troubleshooting

### **direnv not working?**
```bash
# Check if direnv is hooked to your shell
echo $DIRENV_BASH  # Should show path if working

# Re-add to shell config
echo 'eval "$(direnv hook zsh)"' >> ~/.zshrc
source ~/.zshrc
```

### **Environment variables not loading?**
```bash
# Allow the .envrc file
direnv allow

# Check if variables are set
echo $SPIN_VARIABLE_TWILIO_ACCOUNT_SID
```

### **Make commands not working?**
```bash
# Check if make is installed
make --version

# See available commands
make help

# Check environment
make check-env
```

### **Server not starting?**
```bash
# Check if port is already in use
lsof -i :3000

# Kill any existing processes
make stop

# Try again
make dev
```

## 🎉 You're Ready!

With this setup, you have:
- ✅ **Automatic environment management** (direnv)
- ✅ **Simple command interface** (Makefile)
- ✅ **Secure credential handling** (.envrc)
- ✅ **Professional development workflow**

**Boris and Fiona's walk reminders are ready for development!** 🐕🐕✨