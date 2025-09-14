import subprocess

# Define paths
local_font_path = r"C:\Users\D\David\Books\remarkable\MaruBuri-Regular.otf"
remote_font_path = "/usr/share/fonts/MaruBuri-Regular.otf"

local_image_path = r"C:\Users\D\David\Books\remarkable\suspended.png"
remote_image_path = "/usr/share/remarkable/suspended.png"

# Define reMarkable SSH alias (configured in ~/.ssh/config)
remarkable_alias = "reMarkable"

def ssh_run_command(command):
    """Run SSH command with relaxed host checking and no known_hosts issues."""
    ssh_command = (
        f'ssh -o StrictHostKeyChecking=no '
        f'-o UserKnownHostsFile=/dev/null '
        f'{remarkable_alias} "{command}"'
    )
    process = subprocess.run(ssh_command, shell=True, capture_output=True, text=True)
    return process.stdout.strip()

def test_ssh_connection():
    """Check if SSH connection is successful."""
    print("Testing SSH connection to reMarkable...")
    output = ssh_run_command("echo connection_success")

    if "connection_success" in output:
        print("✅ SSH connection established successfully.")
        return True
    else:
        print("❌ SSH connection failed. Please check your SSH key setup.")
        return False

def copy_file(local_path, remote_path):
    """Copy a file from local to reMarkable."""
    scp_command = (
        f"scp -o StrictHostKeyChecking=no "
        f"-o UserKnownHostsFile=/dev/null "
        f"{local_path} {remarkable_alias}:{remote_path}"
    )
    process = subprocess.run(scp_command, shell=True)
    return process.returncode == 0

def check_and_copy_font():
    # Step 1: Check SSH Connection
    if not test_ssh_connection():
        return

    # Step 2: Check if font exists
    print("Checking if font exists on reMarkable...")
    font_status = ssh_run_command(f'test -f {remote_font_path} && echo exists || echo missing')

    print(f"📝 Font check output: {font_status}")  # Debugging statement

    if "missing" in font_status:
        print("🚀 Font not found on reMarkable. Copying now...")
        if copy_file(local_font_path, remote_font_path):
            print("✅ Font copied successfully.")
        else:
            print("❌ Failed to copy font. Please check the connection.")
    else:
        print("✅ Font is already installed on reMarkable.")

    # Step 3: Replace `suspended.png`
    print("🖼️ Replacing suspended.png on reMarkable...")
    if copy_file(local_image_path, remote_image_path):
        print("✅ suspended.png replaced successfully.")
    else:
        print("❌ Failed to replace suspended.png. Please check the connection.")

    # Step 4: Reboot reMarkable
    print("🔄 Rebooting reMarkable...")
    ssh_run_command("/sbin/reboot")
    print("✅ reMarkable has been rebooted.")

# Run the function
check_and_copy_font()
