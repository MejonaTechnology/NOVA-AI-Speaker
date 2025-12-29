# OCI Backend Deployment Guide

Use these commands to deploy the Python Backend to the OCI Server (`161.118.184.207`).

## 1. Transfer Updated Code (SCP)
Run this from your **Local PC Terminal** to update files:
```powershell
# Update main.py (AI logic)
scp -i "D:\Mejona Workspace\Product\Home-Assistant\oci_key_new" "D:\Mejona Workspace\Product\NOVA AI Speaker\backend\main.py" ubuntu@161.118.184.207:~/nova-ai-backend/main.py

# Update tuya_controller.py (Light control)
scp -i "D:\Mejona Workspace\Product\Home-Assistant\oci_key_new" "D:\Mejona Workspace\Product\NOVA AI Speaker\backend\tuya_controller.py" ubuntu@161.118.184.207:~/nova-ai-backend/tuya_controller.py
```

## 2. Restart Server (Fast Update)
If you only changed `main.py` or `tuya_controller.py` code, just restart the container:
```powershell
ssh -i "D:\Mejona Workspace\Product\Home-Assistant\oci_key_new" ubuntu@161.118.184.207 "sudo docker restart nova-ai-backend"
```
**Container Name:** `nova-ai-backend` (not `nova-backend`)

---

## 3. Full Rebuild (Slow Update)
Run this **ONLY** if you changed `requirements.txt`, `Dockerfile`, or added new files like `tuya_controller.py`:

**Method A: Quick Deploy (Copy all files + rebuild):**
```powershell
# Copy all backend files
scp -i "D:\Mejona Workspace\Product\Home-Assistant\oci_key_new" "D:\Mejona Workspace\Product\NOVA AI Speaker\backend\main.py" ubuntu@161.118.184.207:~/nova-ai-backend/
scp -i "D:\Mejona Workspace\Product\Home-Assistant\oci_key_new" "D:\Mejona Workspace\Product\NOVA AI Speaker\backend\tuya_controller.py" ubuntu@161.118.184.207:~/nova-ai-backend/
scp -i "D:\Mejona Workspace\Product\Home-Assistant\oci_key_new" "D:\Mejona Workspace\Product\NOVA AI Speaker\backend\requirements.txt" ubuntu@161.118.184.207:~/nova-ai-backend/
scp -i "D:\Mejona Workspace\Product\Home-Assistant\oci_key_new" "D:\Mejona Workspace\Product\NOVA AI Speaker\backend\Dockerfile" ubuntu@161.118.184.207:~/nova-ai-backend/

# Rebuild container
ssh -i "D:\Mejona Workspace\Product\Home-Assistant\oci_key_new" ubuntu@161.118.184.207 "cd ~/nova-ai-backend && sudo docker stop nova-ai-backend && sudo docker rm nova-ai-backend && sudo docker build -t nova-backend . && sudo docker run -d --name nova-ai-backend -p 8000:8000 --restart unless-stopped -e GROQ_API_KEY='<YOUR_GROQ_API_KEY>' nova-backend"
```

**Method B: Manual Deploy (SSH + commands):**
1. **SSH into Server:**
   ```powershell
   ssh -i "D:\Mejona Workspace\Product\Home-Assistant\oci_key_new" ubuntu@161.118.184.207
   ```

2. **Run Commands (Inside Server):**
   ```bash
   cd ~/nova-ai-backend

   # Stop old container
   sudo docker stop nova-ai-backend
   sudo docker rm nova-ai-backend

   # Build new image
   sudo docker build -t nova-backend .

   # Run new container (get API key from existing .env file)
   GROQ_KEY=$(cat .env | grep GROQ_API_KEY | cut -d'=' -f2)
   sudo docker run -d --name nova-ai-backend -p 8000:8000 --restart unless-stopped -e GROQ_API_KEY="$GROQ_KEY" nova-backend
   ```

## 4. Verify Deployment
Check server status:
```powershell
# Test health endpoint
curl http://nova.mejona.com/

# Check container status
ssh -i "D:\Mejona Workspace\Product\Home-Assistant\oci_key_new" ubuntu@161.118.184.207 "sudo docker ps"

# View logs
ssh -i "D:\Mejona Workspace\Product\Home-Assistant\oci_key_new" ubuntu@161.118.184.207 "sudo docker logs -f nova-ai-backend"
```

## 5. Troubleshooting
Check logs:
```bash
sudo docker logs -f nova-ai-backend
```

**Common Issues:**
- Container name is `nova-ai-backend` (not `nova-backend`)
- Ensure all files are copied: main.py, tuya_controller.py, requirements.txt, Dockerfile
- Check weather API may show connection errors (normal, non-critical)
