# Deploying to AWS EC2 (Free Tier)

Single container, single `t2.micro`/`t3.micro` instance, SQLite on the
instance's own EBS volume. Fits the AWS free tier (750 instance-hours/month
for 12 months, 30GB EBS included). No ALB, no ECS, no EFS — nothing else in
this stack needs them.

## 1. Launch the instance (AWS Console)

- EC2 → Launch instance
- AMI: **Amazon Linux 2023**
- Instance type: **t2.micro** (or t3.micro — both free-tier eligible)
- Key pair: create/select one, download the `.pem` (needed for SSH)
- Storage: default 8GB gp3 is enough (free tier covers up to 30GB)
- Security group inbound rules:
  - SSH (22) — source: **My IP** (not 0.0.0.0/0)
  - HTTP (80) — source: **Anywhere (0.0.0.0/0)**
- Launch

Optional: allocate an **Elastic IP** and associate it with the instance —
free while attached to a running instance, gives you a stable address
instead of one that changes on stop/start.

## 2. SSH in

```bash
chmod 400 your-key.pem
ssh -i your-key.pem ec2-user@<public-ip>
```

## 3. Install Docker

```bash
sudo dnf install -y docker
sudo systemctl enable --now docker
sudo usermod -aG docker ec2-user
exit   # log out, then ssh back in so the group change takes effect
```

## 4. Get the code and build

```bash
sudo dnf install -y git
git clone https://github.com/G26karthik/Throughline.git
cd Throughline
docker build -t throughline .
```

## 5. Run it

```bash
mkdir -p ~/throughline-data
docker run -d --name throughline --restart unless-stopped \
  -p 80:8000 \
  -v ~/throughline-data:/data \
  throughline
```

- `-p 80:8000` — container's uvicorn (port 8000) exposed on the instance's
  port 80, so `http://<public-ip>/` serves the app directly, no reverse
  proxy needed.
- `-v ~/throughline-data:/data` — SQLite file lives on the host EBS volume,
  survives container restarts/redeploys. Deleting the instance deletes it too
  (add S3 backup if that ever matters for this project).
- `--restart unless-stopped` — container comes back up after an instance
  reboot.

Open `http://<public-ip>/` in a browser. The app auto-seeds on first boot if
the database is empty (see `lifespan` in `src/backend/main.py`).

## Updating after a code change

```bash
cd Throughline
git pull
docker build -t throughline .
docker rm -f throughline
docker run -d --name throughline --restart unless-stopped \
  -p 80:8000 -v ~/throughline-data:/data throughline
```

## What's out of scope here

- **HTTPS** — needs a domain pointed at the instance plus Caddy or
  certbot+nginx in front. Skip for a pitch demo on a bare IP; add later if a
  domain shows up.
- **Auto-scaling / multi-instance** — SQLite is single-writer by design here;
  this deploy is intentionally one box, matching the project's "boring,
  auditable stack" choice (see main README).
