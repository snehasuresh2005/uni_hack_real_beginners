import subprocess
import os
import sys
import time

def run():
    workspace = os.path.dirname(os.path.abspath(__file__))
    
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
    # Use shell=True for npm commands on Windows
    frontend_proc = subprocess.Popen(
        ["npm", "run", "dev", "--", "--host", "127.0.0.1", "--port", "5173"],
        cwd=frontend_dir,
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
        
    print("--------------------------------------------------")
    print("Both servers started successfully!")
    print("- Frontend (Vite): http://127.0.0.1:5173")
    print("- Backend (FastAPI): http://127.0.0.1:8000")
    print("Press Ctrl+C to shut down both servers.")
    print("--------------------------------------------------")
    
    try:
        # Keep running and print logs
        while True:
            # Check backend output
            # Non-blocking read (using select or just checking poll)
            if backend_proc.poll() is not None:
                print("Backend terminated.")
                break
            if frontend_proc.poll() is not None:
                print("Frontend terminated.")
                break
            
            # Print any incoming log lines
            # (Just sleep since it is in background)
            time.sleep(1)
    except KeyboardInterrupt:
        print("Shutting down servers...")
    finally:
        backend_proc.terminate()
        frontend_proc.terminate()
        print("Servers stopped.")

if __name__ == "__main__":
    run()
