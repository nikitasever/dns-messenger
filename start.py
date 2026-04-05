"""
Startup script for Railway / cloud deployment.
Launches both the DNS relay server and the web client in one process.
"""

import os
import sys
import threading
import time

def start_relay():
    """Start the DNS relay server in a background thread."""
    from server import RelayServer
    domain = os.environ.get('DNS_DOMAIN', 'msg.tunnel.local')
    relay_port = int(os.environ.get('RELAY_PORT', '15353'))
    relay = RelayServer(domain=domain, bind='127.0.0.1', port=relay_port)
    print(f'[*] Relay server starting on 127.0.0.1:{relay_port}', flush=True)
    relay.run()

def start_web():
    """Start the web client."""
    from web_client import app, socketio, init_admin
    from transport import UDPTransport
    import web_client

    relay_port = int(os.environ.get('RELAY_PORT', '15353'))
    web_port = int(os.environ.get('PORT', '8080'))
    domain = os.environ.get('DNS_DOMAIN', 'msg.tunnel.local')

    web_client.server_ip = '127.0.0.1'
    web_client.server_port = relay_port
    web_client.transport = UDPTransport('127.0.0.1', relay_port, domain)

    init_admin()

    print(f'[*] Web client starting on 0.0.0.0:{web_port}', flush=True)
    print(f'[*] PORT env = {os.environ.get("PORT", "not set")}', flush=True)
    socketio.run(app, host='0.0.0.0', port=web_port,
                 debug=False, allow_unsafe_werkzeug=True)

if __name__ == '__main__':
    # Start relay in background thread
    relay_thread = threading.Thread(target=start_relay, daemon=True)
    relay_thread.start()

    # Give relay a moment to bind
    time.sleep(0.5)

    # Start web (blocks)
    start_web()
