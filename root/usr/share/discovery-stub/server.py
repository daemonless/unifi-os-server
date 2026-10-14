#!/usr/local/bin/python3
"""
Discovery stub — HTTP server on 127.0.0.1:11002
unifi-core calls GET /interfaces to get network interface data.
Parses ifconfig output on FreeBSD (netmask is hex: 0xffffff00).
"""
import http.server
import json
import re
import socket
import struct
import subprocess

def hex_netmask_to_dotted(hex_mask):
    """Convert 0xffffff00 to 255.255.255.0"""
    val = int(hex_mask, 16)
    return socket.inet_ntoa(struct.pack('>I', val))

def prefix_len(netmask):
    """255.255.255.0 -> 24"""
    return bin(struct.unpack('>I', socket.inet_aton(netmask))[0]).count('1')

def get_interfaces():
    result = {}

    # Always include loopback
    result["lo"] = [{
        "address": "127.0.0.1",
        "netmask": "255.0.0.0",
        "family": "IPv4",
        "mac": "00:00:00:00:00:00",
        "internal": True,
        "cidr": "127.0.0.1/8",
        "scopeid": 0
    }]

    try:
        out = subprocess.check_output(["ifconfig"], text=True, stderr=subprocess.DEVNULL)
    except Exception:
        return result

    current = None
    interfaces = []

    def finish_current():
        if current:
            interfaces.append(current)

    for line in out.splitlines():
        # Interface line: "epair0b: flags=..."
        m = re.match(r'^(\S+):', line)
        if m:
            finish_current()
            current = {
                "name": m.group(1),
                "mac": None,
                "entries": [],
            }
            continue

        if current is None:
            continue

        # ether xx:xx:xx:xx:xx:xx
        m = re.search(r'ether\s+([0-9a-f:]{17})', line)
        if m:
            current["mac"] = m.group(1)

        # inet addr netmask mask
        m = re.search(r'inet\s+(\d+\.\d+\.\d+\.\d+)\s+netmask\s+(\S+)', line)
        if m:
            addr = m.group(1)
            mask_raw = m.group(2)
            if mask_raw.startswith('0x'):
                netmask = hex_netmask_to_dotted(mask_raw)
            else:
                netmask = mask_raw
            plen = prefix_len(netmask)
            current["entries"].append((addr, netmask, plen))

    finish_current()

    for iface in interfaces:
        if iface["name"] in ("lo0", "lo"):
            continue
        if not iface["entries"] or not iface["mac"]:
            continue
        addr, netmask, plen = iface["entries"][0]
        result["eth0"] = [{
            "address": addr,
            "netmask": netmask,
            "family": "IPv4",
            "mac": iface["mac"],
            "internal": False,
            "cidr": f"{addr}/{plen}",
            "scopeid": 0
        }]
        break

    return result


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # suppress access logs

    def do_GET(self):
        if self.path == '/interfaces':
            data = get_interfaces()
            body = json.dumps(data).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()


if __name__ == '__main__':
    server = http.server.HTTPServer(('127.0.0.1', 11002), Handler)
    server.serve_forever()
