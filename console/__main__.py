"""console entry point: python -m console"""

from console.app import _bootstrap_admin, app

if __name__ == "__main__":
    _bootstrap_admin()
    app.run(host="0.0.0.0", port=5001)
