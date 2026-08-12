#!/usr/bin/env bash
# One-command deploy for Gesture-Ease on an Ubuntu VM (e.g. Oracle Always Free).
# Model and app code are NOT modified — this only sets up the host and runs the
# existing Docker image. Run on a fresh Ubuntu 22.04 VM:
#
#   curl -fsSL https://raw.githubusercontent.com/shrutz2/Gesture-Ease/main/deploy/oracle-setup.sh | bash
#
set -euo pipefail
echo "==> Gesture-Ease deploy starting..."

# 1) Swap — TensorFlow needs more RAM than a 1 GB free VM has.
if ! sudo swapon --show | grep -q /swapfile; then
  echo "==> Adding 4 GB swap"
  sudo fallocate -l 4G /swapfile
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile
  sudo swapon /swapfile
  echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
fi

# 2) Docker + git
echo "==> Installing Docker + git"
sudo apt-get update -y
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y docker.io git iptables-persistent
sudo systemctl enable --now docker

# 3) Open port 80 at the OS firewall (Oracle Ubuntu images block it by default).
echo "==> Opening port 80"
sudo iptables -I INPUT -p tcp --dport 80 -j ACCEPT || true
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
echo "==> Building image (this can take 15-30 min on a small VM)"
sudo docker build -t gesture-ease .

# 6) Run it — restart on reboot, host port 80 -> container 7860
echo "==> Starting container"
sudo docker rm -f gesture-ease 2>/dev/null || true
JWT=$(openssl rand -hex 32)
sudo docker run -d --restart unless-stopped -p 80:7860 \
  -e JWT_SECRET="$JWT" \
  --name gesture-ease gesture-ease

IP=$(curl -s ifconfig.me || echo "<your-vm-public-ip>")
echo ""
echo "==> Done!  Your app: http://$IP"
echo "    (Also add an Ingress rule for TCP port 80 in the VM's Security List.)"
