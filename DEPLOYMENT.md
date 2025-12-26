# OCI Backend Deployment Guide

Use these commands to deploy the Python Backend to the OCI Server (`161.118.184.207`).

## 1. Transfer Updated Code (SCP)
Run this from your **Local PC Terminal** to update `main.py`:
```powershell
scp -i "D:\Mejona Workspace\Product\Home-Assistant\oci_key_new" "d:\Mejona Workspace\Product\NOVA AI Speaker\backend\main.py" ubuntu@161.118.184.207:~/nova-ai-backend/main.py
```

## 2. Restart Server (Fast Update)
If you only changed `main.py` code, just restart the container:
```powershell
ssh -i "D:\Mejona Workspace\Product\Home-Assistant\oci_key_new" ubuntu@161.118.184.207 "sudo docker restart nova-backend"
```
*(Note: Use `sudo docker ps` to find the container ID if `nova-backend` is not found, or use the ID `94febc3fd6ff`)*.

---

## 3. Full Rebuild (Slow Update)
Run this **ONLY** if you changed `requirements.txt` or `Dockerfile`:

1. **SSH into Server:**
   ```powershell
   ssh -i "D:\Mejona Workspace\Product\Home-Assistant\oci_key_new" ubuntu@161.118.184.207
   ```

2. **Run Commands (Inside Server):**
   ```bash
   cd ~/nova-ai-backend
   
   # Stop old container
   sudo docker stop nova-backend
   sudo docker rm nova-backend
   
   # Build new image
   sudo docker build -t nova-backend .
   
   # Run new container (Replace <YOUR_KEY> with actual Groq API Key)
   sudo docker run -d --name nova-backend -p 8000:8000 --restart unless-stopped -e GROQ_API_KEY="<YOUR_KEY>" nova-backend
   ```

## 4. Troubleshooting
Check logs:
```bash
sudo docker logs -f nova-backend
```
