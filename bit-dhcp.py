import os
import subprocess
import time
import ipaddress
import re
import select
import sys
from datetime import datetime

BOOTPD_FILE = "/etc/bootpd.plist"
BOOTPTAB_FILE = "/etc/bootptab"
COOKIE_STRING = "# Configured by BitBox utility"

def is_bootpd_running():
    try:
        output = subprocess.check_output(["pgrep", "bootpd"]).decode()
        return bool(output.strip())
    except subprocess.CalledProcessError:
        return False

def start_bootpd():
    try:
        subprocess.run(["sudo", "launchctl", "load", "-w", "/System/Library/LaunchDaemons/bootps.plist"], check=True)
        print("bootpd service started successfully.")
    except subprocess.CalledProcessError:
        print("Error: Failed to start bootpd service. Please start it manually.")

def parse_lease_file(file_path):
    leases = []
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Split the content into individual lease blocks
    lease_blocks = content.split('}')[:-1]  # Exclude the last empty element
    
    for block in lease_blocks:
        lease = {}
        for line in block.split('\n'):
            if '=' in line:
                key, value = line.split('=', 1)
                lease[key.strip()] = value.strip().strip('"')
        if lease:
            leases.append(lease)
    
    return leases

def format_leases(leases):
    formatted = "Current DHCP Leases:\n"
    formatted += "-" * 80 + "\n"
    formatted += f"{'IP Address':<15} {'MAC Address':<18} {'Hostname':<20} {'Lease Expires'}\n"
    formatted += "-" * 80 + "\n"
    
    for lease in leases:
        ip = lease.get('ip_address', 'N/A')
        mac = lease.get('hw_address', 'N/A')
        hostname = lease.get('name', 'N/A')
        expires = lease.get('end', 'N/A')
        if expires != 'N/A':
            expires = datetime.fromtimestamp(int(expires)).strftime('%Y-%m-%d %H:%M:%S')
        
        formatted += f"{ip:<15} {mac:<18} {hostname:<20} {expires}\n"
    
    return formatted

def show_ip_leases():
    lease_file = '/var/db/dhcpd_leases'
    last_modified_time = 0
    last_leases = None

    print("Monitoring DHCP leases. Press 'Q' to exit.")

    while True:
        try:
            # Check if there's input available
            if select.select([sys.stdin,], [], [], 0.0)[0]:
                user_input = sys.stdin.readline().strip().lower()
                if user_input == 'q':
                    print("\nExiting IP lease display.")
                    break

            current_modified_time = os.stat(lease_file).st_mtime
            if current_modified_time != last_modified_time:
                leases = parse_lease_file(lease_file)
                if leases != last_leases:
                    print(f"\nChange detected at {time.strftime('%Y-%m-%d %H:%M:%S')}:")
                    print(format_leases(leases))
                    last_leases = leases
                last_modified_time = current_modified_time
            time.sleep(1)  # Check every second
        except Exception as e:
            print(f"Error reading lease file: {e}")
            break

def get_active_network_interfaces():
    all_interfaces = subprocess.check_output(["networksetup", "-listallhardwareports"]).decode()
    active_interfaces = subprocess.check_output(["ifconfig"]).decode()
    active_devices = set(re.findall(r'^(\w+):', active_interfaces, re.MULTILINE))
    
    interfaces = []
    current_name = ""
    current_device = ""
    for line in all_interfaces.split("\n"):
        if line.startswith("Hardware Port:"):
            current_name = line.split(": ")[1]
        elif line.startswith("Device:"):
            current_device = line.split(": ")[1]
            if current_device in active_devices:
                interfaces.append((current_name, current_device))
    
    return interfaces

#confirm that bootpd is set to run at startup
def check_bootpd_startup():
    plist_path = "/System/Library/LaunchDaemons/bootps.plist"
    
    try:
        # Check if the plist file exists
        if not os.path.exists(plist_path):
            print(f"Error: {plist_path} not found. bootpd may not be properly installed.")
            return False

        # Check if bootpd is enabled at startup
        result = subprocess.run(["sudo", "launchctl", "list", "com.apple.bootpd"], 
                                capture_output=True, text=True)
        
        if "com.apple.bootpd" not in result.stdout:
            print("BitBox DHCP Server is not set to run at startup. Setting it up now...")
            subprocess.run(["sudo", "launchctl", "load", "-w", plist_path], check=True)
            print("BitBox DHCP Server has been set to run at startup.")
        else:
            print("BitBox DHCP Server will run at system startup.")
        
        return True

    except subprocess.CalledProcessError as e:
        print(f"Error checking or setting up bootpd startup: {e}")
        return False

def create_new_config():
    interfaces = get_active_network_interfaces()
    print("Available active network interfaces:")
    for i, (name, device) in enumerate(interfaces, 1):
        print(f"{i}. {name} ({device})")

    bitbox_index = next((i for i, (name, device) in enumerate(interfaces) if "bitbox" in name.lower() or "bitbox" in device.lower()), None)

    if bitbox_index is not None:
        print(f"\nAutomatically selected BitBox interface: {interfaces[bitbox_index][0]} ({interfaces[bitbox_index][1]})")
        interface = interfaces[bitbox_index][1]
    else:
        while True:
            choice = input("\nSelect an interface (enter the number): ")
            try:
                interface = interfaces[int(choice) - 1][1]
                break
            except (ValueError, IndexError):
                print("Invalid choice. Please try again.")

    while True:
        start_ip = input("Enter the starting IP address of the range: ")
        if ipaddress.ip_address(start_ip):
            break
        print("Invalid IP address. Please try again.")

    while True:
        end_ip = input("Enter the ending IP address of the range: ")
        if ipaddress.ip_address(end_ip):
            break
        print("Invalid IP address. Please try again.")

    config = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<!--{COOKIE_STRING}-->
<dict>
    <key>bootp_enabled</key>
    <false/>
    <key>detect_other_dhcp_server</key>
    <integer>1</integer>
    <key>dhcp_enabled</key>
    <array>
        <string>{interface}</string>
    </array>
    <key>reply_threshold_seconds</key>
    <integer>0</integer>
    <key>Subnets</key>
    <array>
        <dict>
            <key>allocate</key>
            <true/>
            <key>lease_max</key>
            <integer>86400</integer>
            <key>lease_min</key>
            <integer>86400</integer>
            <key>name</key>
            <string>{'.'.join(start_ip.split('.')[:3])}</string>
            <key>net_address</key>
            <string>{'.'.join(start_ip.split('.')[:3])}.0</string>
            <key>net_mask</key>
            <string>255.255.255.0</string>
            <key>net_range</key>
            <array>
                <string>{start_ip}</string>
                <string>{end_ip}</string>
            </array>
        </dict>
    </array>
    <key>use_server_config_for_dhcp_options</key>
    <true/>
</dict>
</plist>
"""

    with open(BOOTPD_FILE, "w") as f:
        f.write(config)
    print(f"New configuration written to {BOOTPD_FILE}")

def restart_bootpd():
    try:
        subprocess.run(["sudo", "launchctl", "unload", "/System/Library/LaunchDaemons/bootps.plist"], check=True)
        time.sleep(1)  # Give it a moment to fully unload
        subprocess.run(["sudo", "launchctl", "load", "-w", "/System/Library/LaunchDaemons/bootps.plist"], check=True)
        print("bootpd service restarted successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Error restarting bootpd service: {e}")

def make_lease_static():
    lease_file = '/var/db/dhcpd_leases'
    bootptab_file = '/etc/bootptab'
    leases = parse_lease_file(lease_file)
    
    if not leases:
        print("No active leases found.")
        return

    print("\nCurrent leases:")
    for i, lease in enumerate(leases, 1):
        print(f"{i}. IP: {lease.get('ip_address', 'N/A')}, MAC: {lease.get('hw_address', 'N/A')}, Hostname: {lease.get('name', 'N/A')}")
    
    while True:
        choice = input("\nEnter the number of the lease you want to make static (or 'q' to quit): ")
        if choice.lower() == 'q':
            return
        try:
            lease_index = int(choice) - 1
            if 0 <= lease_index < len(leases):
                selected_lease = leases[lease_index]
                break
            else:
                print("Invalid selection. Please try again.")
        except ValueError:
            print("Invalid input. Please enter a number or 'q'.")
    
    hostname = selected_lease.get('name', f"client{lease_index + 1}")
    hw_address = selected_lease['hw_address']
    ip_address = selected_lease['ip_address']

    # Prepare the new entry
    new_entry = f"{hostname.ljust(15)}1       {hw_address.ljust(20)}{ip_address}\n"

    # Read existing bootptab file
    try:
        with open(bootptab_file, 'r') as f:
            content = f.readlines()
    except FileNotFoundError:
        content = ["%%\n", "# hostname      hwtype  hwaddr              ipaddr\n"]

    # Check if the entry already exists and update it, or add a new entry
    entry_updated = False
    for i, line in enumerate(content):
        if hw_address in line or ip_address in line:
            content[i] = new_entry
            entry_updated = True
            break
    
    if not entry_updated:
        content.append(new_entry)

    # Write the updated content back to the file
    try:
        with open(bootptab_file, 'w') as f:
            f.writelines(content)
        print(f"Static lease for {hostname} ({hw_address}) with IP {ip_address} has been added/updated in {bootptab_file}")
        
        # Restart the bootpd service
        print("Restarting bootpd service...")
        restart_bootpd()
    except PermissionError:
        print(f"Error: Permission denied. Please run the script with sudo to modify {bootptab_file} and restart the service")
        return

def delete_static_lease():
    try:
        with open(BOOTPTAB_FILE, 'r') as f:
            lines = f.readlines()
    except FileNotFoundError:
        print(f"Error: {BOOTPTAB_FILE} not found.")
        return
    except PermissionError:
        print(f"Error: Permission denied. Please run the script with sudo to read {BOOTPTAB_FILE}")
        return

    static_leases = [line for line in lines if not line.startswith('#') and line.strip()]

    if not static_leases:
        print("No static leases found.")
        return

    print("\nCurrent static leases:")
    for i, lease in enumerate(static_leases, 1):
        parts = lease.split()
        if len(parts) >= 4:
            hostname, _, hw_address, ip_address = parts[:4]
            print(f"{i}. Hostname: {hostname}, MAC: {hw_address}, IP: {ip_address}")

    while True:
        choice = input("\nEnter the number of the lease you want to delete (or 'q' to quit): ")
        if choice.lower() == 'q':
            return
        try:
            lease_index = int(choice) - 1
            if 0 <= lease_index < len(static_leases):
                del lines[lines.index(static_leases[lease_index])]
                break
            else:
                print("Invalid selection. Please try again.")
        except ValueError:
            print("Invalid input. Please enter a number or 'q'.")

    try:
        with open(BOOTPTAB_FILE, 'w') as f:
            f.writelines(lines)
        print(f"Static lease has been deleted from {BOOTPTAB_FILE}")
        
        # Restart the bootpd service
        print("Restarting bootpd service...")
        restart_bootpd()
    except PermissionError:
        print(f"Error: Permission denied. Please run the script with sudo to modify {BOOTPTAB_FILE} and restart the service")

def main():
        # Ensure bootpd is set to run at startup
    check_bootpd_startup()

    if os.path.exists(BOOTPD_FILE):
        with open(BOOTPD_FILE, 'r') as f:
            content = f.read()
        
        if COOKIE_STRING in content:
            print("Existing BitBox configuration found.")
            if not is_bootpd_running():
                print("Starting bootpd with existing configuration.")
                start_bootpd()
            
            while True:
                print("\n1. Show IP leases")
                print("2. Make a lease static")
                print("3. Delete a static lease")
                print("4. Exit")
                choice = input("Enter your choice (1-3): ")
                
                if choice == '1':
                    print("Press Q at any time to return to the main menu")
                    show_ip_leases()
                elif choice == '2':
                    make_lease_static()
                elif choice =='3':
                    delete_static_lease()
                elif choice == '4':
                    print("Exiting.")
                    break
                else:
                    print("Invalid choice. Please try again.")
        else:
            print("bootpd configuration exists but wasn't created by this utility.")
            choice = input("Do you want to (c)reate new config, (s)tart with existing config, or (q)uit? ").lower()
            if choice == 'c':
                create_new_config()
                start_bootpd()
            elif choice == 's':
                if not is_bootpd_running():
                    start_bootpd()
                    show_ip_leases()
            else:
                print("Exiting.")
    else:
        print(f"No configuration file found at {BOOTPD_FILE}")
        choice = input("Do you want to (c)reate new config or (q)uit? ").lower()
        if choice == 'c':
            create_new_config()
            start_bootpd()
            show_ip_leases()
        else:
            print("Exiting.")

if __name__ == "__main__":
    main()
