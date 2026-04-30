"""
check_env.py — Run this on BOTH laptops and compare the output.
Usage:  python check_env.py
"""
import sys
import platform
import socket

print("=" * 55)
print("PYTHON & OS")
print("=" * 55)
print(f"Python     : {sys.version}")
print(f"OS         : {platform.platform()}")
print(f"Machine    : {platform.machine()}")
print()

print("=" * 55)
print("KEY PACKAGES")
print("=" * 55)
packages = [
    "gradio",
    "pandas",
    "numpy",
    "fastapi",
    "uvicorn",
    "starlette",
    "websockets",
    "httpx",
    "anyio",
    "openpyxl",
    "xlrd",
    "pyarrow",
]
try:
    import importlib.metadata as _m
    for pkg in packages:
        try:
            print(f"  {pkg:<18}: {_m.version(pkg)}")
        except _m.PackageNotFoundError:
            print(f"  {pkg:<18}: *** NOT INSTALLED ***")
except ImportError:
    import pkg_resources
    for pkg in packages:
        try:
            print(f"  {pkg:<18}: {pkg_resources.get_distribution(pkg).version}")
        except Exception:
            print(f"  {pkg:<18}: *** NOT INSTALLED ***")

print()
print("=" * 55)
print("NETWORK / PROXY")
print("=" * 55)
import os
for var in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "NO_PROXY"]:
    val = os.environ.get(var)
    if val:
        print(f"  {var}: {val}")
    else:
        print(f"  {var}: (not set)")

# Check if localhost port is reachable
port = 7861
try:
    with socket.create_connection(("127.0.0.1", port), timeout=1):
        print(f"\n  Port {port}: OPEN (another instance may be running)")
except OSError:
    print(f"\n  Port {port}: available (nothing listening — expected before launch)")

print()
print("=" * 55)
print("GRADIO DETAILS")
print("=" * 55)
try:
    import gradio as gr
    print(f"  gradio version : {gr.__version__}")
    # Check if queue API exists in this version
    has_queue = hasattr(gr.Blocks, "queue")
    print(f"  Blocks.queue() : {'available' if has_queue else 'MISSING — upgrade gradio'}")
except ImportError:
    print("  gradio: NOT INSTALLED")

print()
print("Copy the above output and share it alongside the other laptop's output.")




"""
=======================================================
PYTHON & OS
=======================================================
Python     : 3.10.18 | packaged by Anaconda, Inc. | (main, Jun  5 2025, 13:08:55) [MSC v.1929 64 bit (AMD64)]
OS         : Windows-10-10.0.26200-SP0
Machine    : AMD64

=======================================================
KEY PACKAGES
=======================================================
  gradio            : 6.3.0
  pandas            : 2.2.3
  numpy             : 2.2.6
  fastapi           : 0.128.0
  uvicorn           : 0.40.0
  starlette         : 0.50.0
  websockets        : *** NOT INSTALLED ***
  httpx             : 0.28.1
  anyio             : 4.10.0
  openpyxl          : 3.1.5
  xlrd              : *** NOT INSTALLED ***
  pyarrow           : 21.0.0

=======================================================
NETWORK / PROXY
=======================================================
  HTTP_PROXY: (not set)
  HTTPS_PROXY: (not set)
  http_proxy: (not set)
  https_proxy: (not set)
  NO_PROXY: (not set)

  Port 7861: OPEN (another instance may be running)

=======================================================
GRADIO DETAILS
=======================================================
  gradio version : 6.3.0
  Blocks.queue() : available

"""