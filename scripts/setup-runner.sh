#!/usr/bin/env bash
set -e

REPO_URL="https://github.com/zhou-en/pyppeteer-scraper"
RUNNER_DIR="$HOME/actions-runner"

echo "=== GitHub Actions self-hosted runner setup ==="
echo ""
read -rp "Paste your registration token (from GitHub repo → Settings → Actions → Runners): " TOKEN

# Detect architecture
ARCH=$(uname -m)
if [ "$ARCH" = "aarch64" ]; then
  RUNNER_ARCH="arm64"
elif [ "$ARCH" = "armv7l" ]; then
  RUNNER_ARCH="arm"
else
  RUNNER_ARCH="x64"
fi
echo "Detected arch: $ARCH → using runner arch: $RUNNER_ARCH"

# Get latest runner version
echo "Fetching latest runner version..."
RUNNER_VERSION=$(curl -s https://api.github.com/repos/actions/runner/releases/latest \
  | grep '"tag_name"' | sed 's/.*"v\([^"]*\)".*/\1/')
echo "Runner version: $RUNNER_VERSION"

mkdir -p "$RUNNER_DIR" && cd "$RUNNER_DIR"

# Download and extract
TARBALL="actions-runner-linux-${RUNNER_ARCH}-${RUNNER_VERSION}.tar.gz"
echo "Downloading $TARBALL..."
curl -fsSL -o "$TARBALL" \
  "https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/${TARBALL}"
tar xzf "$TARBALL"
rm "$TARBALL"

# Configure
echo ""
echo "Configuring runner..."
./config.sh \
  --url "$REPO_URL" \
  --token "$TOKEN" \
  --name "pi-runner" \
  --labels "self-hosted,pi" \
  --unattended

# Install and start as a systemd service
echo ""
echo "Installing as systemd service..."
sudo ./svc.sh install
sudo ./svc.sh start

echo ""
echo "=== Done! Runner is running as a background service ==="
echo "Check status: sudo ~/actions-runner/svc.sh status"
echo "View logs:    sudo journalctl -u actions.runner.* -f"
