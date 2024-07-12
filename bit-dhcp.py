import subprocess
import ipaddress
import re
import os
import xml.etree.ElementTree as ET
import xml.dom.minidom as minidom

BOOTPD_FILE = "/etc/bootpd.plist"
COOKIE_STRING = "# Configured by BitBox utility"

def get_active_network_interfaces():
    all_interfaces = subprocess.check_output(["networksetup", "-listallhardwareports"]).decode()
    active_interfaces = subprocess.check_output(["ifconfig"]).decode()
    active_devices = re.findall(r'^(\w+):', active_interfaces, re.MULTILINE)
    
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

def validate_ip(ip):
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False

def read_existing_config():
    if os.path.exists(BOOTPD_FILE):
        with open(BOOTPD_FILE, "r") as f:
            content = f.read()
        if COOKIE_STRING in content:
            match = re.search(r'net (\w+)\s+netrange (\S+) (\S+)', content)
            if match:
                return match.groups()
    return None

def write_config(interface, start_ip, end_ip):
    root = ET.Element("plist", version="1.0")
    doc_type = '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">'
    
    dict_elem = ET.SubElement(root, "dict")
    
    ET.SubElement(dict_elem, "key").text = "bootp_enabled"
    ET.SubElement(dict_elem, "false")
    
    ET.SubElement(dict_elem, "key").text = "detect_other_dhcp_server"
    ET.SubElement(dict_elem, "integer").text = "1"
    
    ET.SubElement(dict_elem, "key").text = "dhcp_enabled"
    array_elem = ET.SubElement(dict_elem, "array")
    ET.SubElement(array_elem, "string").text = interface
    
    ET.SubElement(dict_elem, "key").text = "reply_threshold_seconds"
    ET.SubElement(dict_elem, "integer").text = "0"
    
    ET.SubElement(dict_elem, "key").text = "Subnets"
    subnets_array = ET.SubElement(dict_elem, "array")
    subnet_dict = ET.SubElement(subnets_array, "dict")
    
    ET.SubElement(subnet_dict, "key").text = "allocate"
    ET.SubElement(subnet_dict, "true")
    
    ET.SubElement(subnet_dict, "key").text = "lease_max"
    ET.SubElement(subnet_dict, "integer").text = "86400"
    
    ET.SubElement(subnet_dict, "key").text = "lease_min"
    ET.SubElement(subnet_dict, "integer").text = "86400"
    
    ET.SubElement(subnet_dict, "key").text = "name"
    ET.SubElement(subnet_dict, "string").text = ".".join(start_ip.split(".")[:3])
    
    ET.SubElement(subnet_dict, "key").text = "net_address"
    ET.SubElement(subnet_dict, "string").text = f"{'.'.join(start_ip.split('.')[:3])}.0"
    
    ET.SubElement(subnet_dict, "key").text = "net_mask"
    ET.SubElement(subnet_dict, "string").text = "255.255.255.0"
    
    ET.SubElement(subnet_dict, "key").text = "net_range"
    net_range_array = ET.SubElement(subnet_dict, "array")
    ET.SubElement(net_range_array, "string").text = start_ip
    ET.SubElement(net_range_array, "string").text = end_ip
    
    ET.SubElement(dict_elem, "key").text = "use_server_config_for_dhcp_options"
    ET.SubElement(dict_elem, "true")
    
    xml_str = ET.tostring(root, encoding="unicode")
    pretty_xml = minidom.parseString(xml_str).toprettyxml(indent="  ")
    
    # Remove extra newlines that minidom adds
    pretty_xml = '\n'.join([line for line in pretty_xml.split('\n') if line.strip()])
    
    # Add the DOCTYPE after the XML declaration
    pretty_xml = pretty_xml.replace('<?xml version="1.0" ?>', f'<?xml version="1.0" encoding="UTF-8"?>\n{doc_type}')
    
    try:
        with open(BOOTPD_FILE, "w") as f:
            f.write(pretty_xml)
        print(f"Configuration written to {BOOTPD_FILE}")
    except PermissionError:
        print(f"Error: Permission denied. Try running the script with sudo.")

def is_bootpd_running():
    try:
        output = subprocess.check_output(["sudo", "launchctl", "list", "com.apple.bootpd"]).decode()
        return "com.apple.bootpd" in output
    except subprocess.CalledProcessError:
        return False

def start_bootpd():
    try:
        subprocess.run(["sudo", "launchctl", "load", "-w", "/System/Library/LaunchDaemons/bootps.plist"], check=True)
        print("bootpd service started successfully.")
    except subprocess.CalledProcessError:
        print("Error: Failed to start bootpd service. Please start it manually.")

def main():
    existing_config = read_existing_config()
    if existing_config:
        print("Existing configuration found:")
        print(f"Interface: {existing_config[0]}")
        print(f"IP range: {existing_config[1]} - {existing_config[2]}")
        reuse = input("Do you want to reuse this configuration? (y/n): ").lower()
        if reuse == 'y':
            write_config(*existing_config)
            if not is_bootpd_running():
                start_bootpd()
            return

    interfaces = get_active_network_interfaces()
    if not interfaces:
        print("No active network interfaces found.")
        return
    
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
        if validate_ip(start_ip):
            break
        print("Invalid IP address. Please try again.")

    while True:
        end_ip = input("Enter the ending IP address of the range: ")
        if validate_ip(end_ip):
            break
        print("Invalid IP address. Please try again.")

    write_config(interface, start_ip, end_ip)

    if not is_bootpd_running():
        start_bootpd()

if __name__ == "__main__":
    main()
