import subprocess
import os
import sys
import time

def free_ports():
    """Kill any processes holding our dev ports to prevent EADDRINUSE on restart."""
    import subprocess, sys
    ports = [8000, 5173, 3001]
    for port in ports:
        try:
            # Find PID listening on the port
            result = subprocess.run(
                ["netstat", "-ano"],
                capture_output=True, text=True
            )
            for line in result.stdout.splitlines():
                if f":{port} " in line and "LISTENING" in line:
                    parts = line.strip().split()
                    pid = parts[-1]
                    if pid and pid != "0":
                        subprocess.run(["taskkill", "/F", "/PID", pid],
                                       capture_output=True)
        except Exception:
            pass

def run():
    workspace = os.path.dirname(os.path.abspath(__file__))

    # Free any ports still held by a previous session
    free_ports()
    time.sleep(1)
    
    # 1. Start backend FastAPI server
    backend_dir = os.path.join(workspace, "backend")
    print("Starting FastAPI backend server...")
    backend_proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.app:app", "--host", "127.0.0.1", "--port", "8000"],
        cwd=workspace,
        env={**os.environ, "PYTHONPATH": workspace}
    )
    
    # 2. Start frontend Vite dev server
    frontend_dir = os.path.join(workspace, "frontend")
    print("Starting Vite frontend server...")
    frontend_proc = subprocess.Popen(
        "npm run dev",
        cwd=frontend_dir,
        shell=True,
        env={**os.environ}
    )
    
    # 3. Start freellmapi proxy server (Port 3001)
    freellm_dir = os.path.join(workspace, "freellmapi")
    freellm_data_dir = os.path.join(freellm_dir, "server", "data")
    os.makedirs(freellm_data_dir, exist_ok=True)
    freellm_db_path = os.path.join(freellm_data_dir, "freeapi.db")
    
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    try:
        import sqlite3
        conn = sqlite3.connect(freellm_db_path)
        conn.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
        if gemini_key:
            conn.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES ('unified_api_key', ?)",
                (gemini_key,)
            )
        conn.commit()
        conn.close()
        print("Seeded freellmapi database.")
    except Exception as e:
        print(f"Warning: Could not seed freellmapi database: {e}")

    print("Starting freellmapi server...")
    freellm_env = {**os.environ}
    if gemini_key:
        freellm_env["FREEAPI_CONFIG_JSON"] = '{"keys":[{"platform":"google","key":"' + gemini_key + '"}]}'
    freellm_proc = subprocess.Popen(
        ["npm", "run", "dev", "-w", "server"],
        cwd=freellm_dir,
        env=freellm_env,
        shell=True
    )
    
    time.sleep(3)
    
    # Check if processes are running
    if backend_proc.poll() is not None:
        print("Error: Backend failed to start.")
        return
        
    if frontend_proc.poll() is not None:
        print("Error: Frontend failed to start.")
        return
        
    if freellm_proc.poll() is not None:
        print("Error: freellmapi failed to start.")
        return
        
    print("--------------------------------------------------")
    print("All servers started successfully!")
    print("- Frontend (Vite): http://127.0.0.1:5173")
    print("- Backend (FastAPI): http://127.0.0.1:8000")
    print("- Proxy (freellmapi): http://127.0.0.1:3001")
    print("Press Ctrl+C to shut down all servers.")
    print("--------------------------------------------------")
    
    try:
        # Keep running and print logs
        while True:
            if backend_proc.poll() is not None:
                print("Backend terminated.")
                break
            if frontend_proc.poll() is not None:
                print("Frontend terminated.")
                break
            if freellm_proc.poll() is not None:
                print("freellmapi terminated.")
                break
            time.sleep(1)
    except KeyboardInterrupt:
        print("Shutting down servers...")
    finally:
        backend_proc.terminate()
        frontend_proc.terminate()
        freellm_proc.terminate()
        print("Servers stopped.")

if __name__ == "__main__":
    run()
