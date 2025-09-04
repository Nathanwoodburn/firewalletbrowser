#!/usr/bin/env bash

install_command=""


# Check if OS is using apt package manager (Debian/Ubuntu)

if command -v apt-get &> /dev/null; then
    install_command="sudo apt-get install -y"
    dependencies=(git curl wget python3 python3-pip python3-venv)
    echo "Detected apt package manager."
# Check if OS is using pacman package manager (Arch Linux)
elif command -v pacman &> /dev/null; then
    install_command="sudo pacman -S"
    dependencies=(git curl wget python3 python-pip)
    echo "Detected pacman package manager."
else
    echo "Unsupported package manager. Please install dependencies manually."
    exit 1
fi

# List of dependencies to install
# Install dependencies
for package in "${dependencies[@]}"; do
    # Check if the package is already installed
    if command -v $package &> /dev/null || dpkg -s $package &> /dev/null || pacman -Qi $package &> /dev/null; then
        echo "$package is already installed."
        continue
    fi


    echo "Installing $package..."
    $install_command $package
    # Check if the installation was successful
    if [ $? -ne 0 ]; then
        echo "Failed to install $package. Please check your package manager settings."
        exit 1
    fi
done

if ! command -v node &> /dev/null || ! command -v npm &> /dev/null; then
    echo "Installing Node.js and npm..."
    # Download and install nvm:
    curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash
    # in lieu of restarting the shell
    \. "$HOME/.nvm/nvm.sh"
    nvm install 20

    if [ $? -ne 0 ]; then
        echo "Failed to install Node.js and npm. Please install them manually."
        exit 1
    fi
else
    echo "Node.js and npm are already installed."
fi

# Clone repo
git clone https://git.woodburn.au/nathanwoodburn/firewalletbrowser.git

# Setup venv
cd firewalletbrowser || exit 1
python3 -m venv .venv
source .venv/bin/activate

# Install python dependencies
python3 -m pip install -r requirements.txt

# Write .env file
if [ ! -f ".env" ]; then
    echo "Creating .env file..."
    echo "INTERNAL_HSD=true" > .env
    echo "Created .env file with INTERNAL Node enabled."
fi

echo "Installation complete. You can start the application by running ./start.sh"
