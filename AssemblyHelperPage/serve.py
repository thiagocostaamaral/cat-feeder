import http.server
import socketserver
import socket
import os
import sys

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
DIR = os.path.dirname(os.path.abspath(__file__))


def get_lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIR, **kwargs)


def main():
    ip = get_lan_ip()
    with socketserver.TCPServer(("0.0.0.0", PORT), Handler) as httpd:
        print("Serving AssemblyHelperPage at:")
        print(f"  http://{ip}:{PORT}")
        print("Open that URL on your phone (same Wi-Fi network).")
        print("Press Ctrl+C to stop.")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nStopped.")


if __name__ == "__main__":
    main()
