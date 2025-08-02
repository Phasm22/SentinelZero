#!/usr/bin/env python3

# Test the incomplete XML handling
xml_content = '''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE nmaprun>
<?xml-stylesheet href="file:///opt/homebrew/bin/../share/nmap/nmap.xsl" type="text/xsl"?>
<!-- Nmap 7.97 scan initiated Tue Jul 29 12:31:16 2025 as: nmap -v -T4 -sS -p- --open -n -Pn --disable-arp-ping -oX scan_output.xml 192.168.68.0/24 -->
<nmaprun scanner="nmap" args="nmap -v -T4 -sS -p- --open -n -Pn --disable-arp-ping -oX scan_output.xml 192.168.68.0/24" start="1753813876" startstr="Tue Jul 29 12:31:16 2025" version="7.97" xmloutputversion="1.05">
<scaninfo type="syn" protocol="tcp" numservices="65535" services="1-65535"/>
<verbose level="1"/>
<debugging level="0"/>
<taskbegin task="SYN Stealth Scan" time="1753813876"/>
<taskprogress task="SYN Stealth Scan" time="1753813907" percent="5.64" remaining="520" etc="1753814426"/>
<taskprogress task="SYN Stealth Scan" time="1753813937" percent="12.03" remaining="447" etc="1753814383"/>
<taskprogress task="SYN Stealth Scan" time="1753813967" percent="18.49"'''

print('Testing incomplete XML handling...')
print(f'XML length: {len(xml_content)} characters')
print(f'XML ends with: {repr(xml_content[-50:])}')
print(f'Ends with </nmaprun>: {xml_content.strip().endswith("</nmaprun>")}')
print(f'Contains <host: {"<host" in xml_content}')
print(f'Contains </host>: {"</host>" in xml_content}')

# Simulate the fix
if not xml_content.strip().endswith('</nmaprun>'):
    print("XML is incomplete - needs fixing")
    
    # Try to salvage what we can by finding the last complete element
    xml_content_fixed = xml_content.rstrip()
    
    # Look for incomplete tags at the end and remove them
    lines = xml_content_fixed.split('\n')
    while lines:
        last_line = lines[-1].strip()
        # If the last line looks like an incomplete tag, remove it
        if ('<' in last_line and not last_line.endswith('>')) or \
           (last_line.endswith('"') and not last_line.endswith('"/>') and not last_line.endswith('">')):
            print(f'Removing incomplete line: {last_line[:50]}...')
            lines.pop()
        else:
            break
    
    xml_content_fixed = '\n'.join(lines)
    
    # Now add any missing closing tags
    if '<host' in xml_content_fixed and '</host>' not in xml_content_fixed:
        # Add missing host closing tags
        open_hosts = xml_content_fixed.count('<host') - xml_content_fixed.count('</host>')
        for _ in range(open_hosts):
            xml_content_fixed += '</host>'
        print(f'Added {open_hosts} missing host closing tags')
    
    # Close the nmaprun element
    xml_content_fixed += '</nmaprun>'
    print(f'Added closing nmaprun tag')
    print(f"Fixed XML ends with: {repr(xml_content_fixed[-50:])}")
        
    # Test if fixed XML is parseable
    try:
        import xml.etree.ElementTree as ET
        root = ET.fromstring(xml_content_fixed)
        print("✅ Fixed XML is parseable!")
        print(f"Root element: {root.tag}")
        hosts = root.findall('host')
        print(f"Found {len(hosts)} host elements")
    except Exception as e:
        print(f"❌ Fixed XML still not parseable: {e}")
        # Debug the XML
        lines = xml_content_fixed.split('\n')
        for i, line in enumerate(lines[:6], 1):
            print(f"Line {i}: {line}")
            if i == 4:
                print(f"         {''.ljust(80)}^")
                print(f"         Position 81: {repr(line[80:85]) if len(line) > 80 else 'EOL'}")
                
else:
    print("XML is complete")
