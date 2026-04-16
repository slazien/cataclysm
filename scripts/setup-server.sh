#!/bin/bash
# Cataclysm VPS Setup — dual environment (prod + staging)
# Run as root on a fresh Ubuntu 24.04 Hetzner server.
set -euo pipefail

echo "=== Cataclysm VPS Setup (dual-env) ==="

# -- 1. System updates --------------------------------------------------------
echo "[1/9] Updating system packages..."
apt-get update && apt-get upgrade -y

# -- 2. Install Docker --------------------------------------------------------
echo "[2/9] Installing Docker..."
apt-get install -y ca-certificates curl gnupg
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg

echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  > /etc/apt/sources.list.d/docker.list

apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
systemctl enable docker && systemctl start docker
echo "Docker: $(docker --version)"

# -- 3. fail2ban --------------------------------------------------------------
echo "[3/9] Installing fail2ban..."
apt-get install -y fail2ban
systemctl enable fail2ban && systemctl start fail2ban

# -- 4. UFW firewall ----------------------------------------------------------
echo "[4/9] Configuring UFW..."
apt-get install -y ufw
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
echo "y" | ufw enable
ufw status

# -- 5. Harden SSH ------------------------------------------------------------
echo "[5/9] Hardening SSH (key-only)..."
sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
sed -i 's/^#\?ChallengeResponseAuthentication.*/ChallengeResponseAuthentication no/' /etc/ssh/sshd_config
systemctl restart sshd

# -- 6. Deploy user ------------------------------------------------------------
echo "[6/9] Creating deploy user..."
if ! id -u deploy &>/dev/null; then
    adduser --disabled-password --gecos "Deploy User" deploy
    usermod -aG docker deploy
    mkdir -p /home/deploy/.ssh
    cp /root/.ssh/authorized_keys /home/deploy/.ssh/authorized_keys
    chown -R deploy:deploy /home/deploy/.ssh
    chmod 700 /home/deploy/.ssh
    chmod 600 /home/deploy/.ssh/authorized_keys
    echo "Deploy user created"
else
    echo "Deploy user already exists"
fi

# -- 7. Create directories ----------------------------------------------------
echo "[7/9] Creating application directories..."
mkdir -p /opt/cataclysm/{prod,staging}
mkdir -p /opt/backups/{prod,staging}
mkdir -p /opt/cataclysm/metrics
chown -R deploy:deploy /opt/cataclysm /opt/backups

# -- 8. Install rclone for offsite backups ------------------------------------
echo "[8/9] Installing rclone..."
if ! command -v rclone &>/dev/null; then
    curl https://rclone.org/install.sh | bash
    echo "rclone installed: $(rclone version | head -1)"
    echo ""
    echo "  Configure B2 remote (as deploy user):"
    echo "    su - deploy"
    echo "    rclone config"
    echo "    → New remote → name: b2 → type: b2 → account + key"
else
    echo "rclone already installed"
fi

# -- 9. Cron jobs --------------------------------------------------------------
echo "[9/9] Installing cron jobs..."

CRON_CONTENT=$(cat <<'CRON'
# Postgres backups — twice daily, both envs
0 3,15 * * * /opt/cataclysm/prod/scripts/pg_backup.sh prod >> /var/log/backup-prod.log 2>&1
5 3,15 * * * /opt/cataclysm/staging/scripts/pg_backup.sh staging >> /var/log/backup-staging.log 2>&1

# App data offsite sync — daily at 04:00
0 4 * * * rclone sync /var/lib/docker/volumes/prod_app_data/_data/ b2:cataclysm-backups/app-data/ --transfers 1 >> /var/log/backup-appdata.log 2>&1

# Weekly restore test — Monday 05:00
0 5 * * 1 /opt/cataclysm/prod/scripts/test_restore.sh >> /var/log/restore-test.log 2>&1
CRON
)

echo "$CRON_CONTENT" | crontab -u deploy -

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "  1. As deploy user:"
echo "       su - deploy"
echo "       docker login ghcr.io -u YOUR_GITHUB_USER"
echo ""
echo "  2. Clone repo into both dirs:"
echo "       git clone https://github.com/slazien/cataclysm.git /opt/cataclysm/prod"
echo "       cd /opt/cataclysm/prod && git checkout main"
echo "       git clone https://github.com/slazien/cataclysm.git /opt/cataclysm/staging"
echo "       cd /opt/cataclysm/staging && git checkout staging"
echo ""
echo "  3. Create .env files:"
echo "       cp /opt/cataclysm/prod/.env.example /opt/cataclysm/prod/.env"
echo "       cp /opt/cataclysm/staging/.env.example /opt/cataclysm/staging/.env.staging"
echo "       # Edit both with real secrets"
echo ""
echo "  4. Configure rclone for B2:"
echo "       rclone config  # add b2 remote"
echo ""
echo "  5. Start prod first (creates shared network):"
echo "       cd /opt/cataclysm/prod"
echo "       docker compose -f docker-compose.prod.yml up -d"
echo ""
echo "  6. Start staging:"
echo "       cd /opt/cataclysm/staging"
echo "       docker compose -f docker-compose.staging.yml up -d"
echo ""
echo "  7. Verify:"
echo "       curl https://cataclysm.one/health"
echo "       curl https://staging.cataclysm.one/health"
