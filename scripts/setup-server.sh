#!/bin/bash
# Cataclysm VPS Initial Setup Script
# Run as root on a fresh Ubuntu 24.04 server
set -euo pipefail

echo "=== Cataclysm VPS Setup ==="

# -- 1. System updates --------------------------------------------------------
echo "[1/8] Updating system packages..."
apt-get update && apt-get upgrade -y

# -- 2. Install Docker via official repo --------------------------------------
echo "[2/8] Installing Docker..."
apt-get install -y ca-certificates curl gnupg
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg

echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  > /etc/apt/sources.list.d/docker.list

apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

systemctl enable docker
systemctl start docker
echo "Docker version: $(docker --version)"

# -- 3. Install and enable fail2ban ------------------------------------------
echo "[3/8] Installing fail2ban..."
apt-get install -y fail2ban
systemctl enable fail2ban
systemctl start fail2ban

# -- 4. Configure UFW firewall -----------------------------------------------
echo "[4/8] Configuring UFW firewall..."
apt-get install -y ufw
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp   # SSH
ufw allow 80/tcp   # HTTP
ufw allow 443/tcp  # HTTPS
echo "y" | ufw enable
ufw status

# -- 5. Disable SSH password auth (key-only) ----------------------------------
echo "[5/8] Hardening SSH..."
sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
sed -i 's/^#\?ChallengeResponseAuthentication.*/ChallengeResponseAuthentication no/' /etc/ssh/sshd_config
systemctl restart sshd

# -- 6. Create deploy user ----------------------------------------------------
echo "[6/8] Creating deploy user..."
if ! id -u deploy &>/dev/null; then
    adduser --disabled-password --gecos "Deploy User" deploy
    usermod -aG docker deploy
    mkdir -p /home/deploy/.ssh
    # Copy root's authorized_keys so the same SSH key works
    cp /root/.ssh/authorized_keys /home/deploy/.ssh/authorized_keys
    chown -R deploy:deploy /home/deploy/.ssh
    chmod 700 /home/deploy/.ssh
    chmod 600 /home/deploy/.ssh/authorized_keys
    echo "Deploy user created with Docker access"
else
    echo "Deploy user already exists"
fi

# -- 7. Create directories and clone repo ------------------------------------
echo "[7/8] Setting up application directories..."
mkdir -p /opt/cataclysm /opt/backups
chown deploy:deploy /opt/cataclysm /opt/backups

echo "Clone the repository as the deploy user:"
echo "  su - deploy"
echo "  git clone https://github.com/slazien/cataclysm.git /opt/cataclysm"
echo "  cd /opt/cataclysm && git checkout main-hetzner"

# -- 8. Install daily backup cron job ----------------------------------------
echo "[8/8] Setting up daily backup cron job..."
CRON_LINE="0 3 * * * /opt/cataclysm/scripts/pg_backup.sh >> /var/log/pg_backup.log 2>&1"
(crontab -l 2>/dev/null | grep -v pg_backup; echo "$CRON_LINE") | crontab -

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "  1. Clone repo:       su - deploy && git clone ... /opt/cataclysm"
echo "  2. Create .env:      cp /opt/cataclysm/.env.example /opt/cataclysm/.env"
echo "  3. Edit .env:         nano /opt/cataclysm/.env"
echo "  4. Docker login:     docker login ghcr.io -u YOUR_GITHUB_USER"
echo "  5. Start services:   cd /opt/cataclysm && docker compose -f docker-compose.prod.yml up -d"
echo "  6. Verify:           curl http://localhost/health"
