#!/usr/bin/env bash
# One-command deploy for Gesture-Ease on an Ubuntu VM (e.g. Oracle Always Free).
# Model and app code are NOT modified — this only sets up the host and runs the
# existing Docker image, with automatic HTTPS (needed so the browser webcam works).
#
# Run on a fresh Ubuntu 22.04 VM:
#   curl -fsSL https://raw.githubusercontent.com/shrutz2/Gesture-Ease/main/deploy/oracle-setup.sh | bash
#
set -euo pipefail
echo "==> Gesture-Ease deploy starting..."

PUBLIC_IP=$(curl -s ifconfig.me)
HOST="${PUBLIC_IP}.nip.io"   # free hostname that resolves to this IP (no domain needed)
echo "==> Public IP: $PUBLIC_IP   Hostname: $HOST"

# 1) Swap — TensorFlow needs more RAM than a 1 GB free VM has.
if ! sudo swapon --show | grep -q /swapfile; then
  echo "==> Adding 4 GB swap"
  sudo fallocate -l 4G /swapfile
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile
  sudo swapon /swapfile
  echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
fi

# 2) Docker, git, Caddy (reverse proxy that gets HTTPS certs automatically)
echo "==> Installing Docker, git, Caddy"
sudo apt-get update -y
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y docker.io git iptables-persistent debian-keyring debian-archive-keyring apt-transport-https curl
sudo systemctl enable --now docker
if ! command -v caddy >/dev/null; then
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list >/dev/null
  sudo apt-get update -y
  sudo apt-get install -y caddy
fi

# 3) Open ports 80 + 443 at the OS firewall (Oracle Ubuntu blocks them by default).
echo "==> Opening ports 80 and 443"
sudo iptables -I INPUT -p tcp --dport 80 -j ACCEPT || true
sudo iptables -I INPUT -p tcp --dport 443 -j ACCEPT || true
sudo netfilter-persistent save || true

# 4) Get the code
cd ~
if [ -d Gesture-Ease ]; then
  cd Gesture-Ease && git pull --ff-only || true
else
  git clone https://github.com/shrutz2/Gesture-Ease.git
  cd Gesture-Ease
fi

# 5) Build the image (React build + Flask + model + videos, one service)
echo "==> Building image (15-30 min on a small VM)"
sudo docker build -t gesture-ease .

# 6) Run the app on localhost:8080 (Caddy will put HTTPS in front)
echo "==> Starting container"
sudo docker rm -f gesture-ease 2>/dev/null || true
JWT=$(openssl rand -hex 32)
sudo docker run -d --restart unless-stopped -p 127.0.0.1:8080:7860 \
  -e JWT_SECRET="$JWT" \
  --name gesture-ease gesture-ease

# 7) Configure Caddy: automatic HTTPS for <ip>.nip.io -> app on :8080
echo "==> Configuring HTTPS via Caddy"
sudo tee /etc/caddy/Caddyfile >/dev/null <<EOF
${HOST} {
    reverse_proxy 127.0.0.1:8080
}
EOF
sudo systemctl restart caddy

echo ""
echo "=========================================================="
echo "  Done!  Your live app (HTTPS, webcam works):"
echo "      https://${HOST}"
echo ""
echo "  If it doesn't load, make sure the VM's Security List has"
echo "  Ingress rules for TCP 80 and 443 from 0.0.0.0/0."
echo "=========================================================="
