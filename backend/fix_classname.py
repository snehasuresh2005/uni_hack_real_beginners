import os

def fix():
    path = r"c:\Users\Sneha\projects\unihack_real_beginners\frontend\src\App.jsx"
    if not os.path.exists(path):
        print("File not found")
        return
        
    with open(path, "r", encoding="utf-8") as f:
        code = f.read()
        
    # Replace class=" with className="
    fixed_code = code.replace('class="', 'className="')
    
    with open(path, "w", encoding="utf-8") as f:
        f.write(fixed_code)
        
    print("Successfully replaced class with className in App.jsx")

if __name__ == "__main__":
    fix()
