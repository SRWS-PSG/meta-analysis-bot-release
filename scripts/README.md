# Scripts Directory

This directory contains utility scripts for deployment and setup.

## Scripts

### `add_redis.sh`
- **Purpose**: Add Redis addon to Heroku app
- **Usage**: `./scripts/add_redis.sh`
- **Note**: For Unix/Linux/Mac systems

### `add_redis_direct.sh`
- **Purpose**: Add Redis addon to Heroku app (Windows-specific version)
- **Usage**: Run from Windows command prompt
- **Note**: Uses direct Heroku API call for Windows compatibility

### `install_heroku_wsl.sh`
- **Purpose**: Install Heroku CLI on Windows Subsystem for Linux (WSL)
- **Usage**: `./scripts/install_heroku_wsl.sh`
- **Note**: Only needed for WSL environments

## Prerequisites

- Heroku CLI installed (except for `install_heroku_wsl.sh`)
- Valid Heroku account with appropriate permissions
- For Redis scripts: Heroku app must already exist