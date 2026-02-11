"""Entry point for the SkyCalc application."""

import argparse
import webbrowser
from threading import Timer


def main():
    """Run the SkyCalc application."""
    parser = argparse.ArgumentParser(
        description="SkyCalc - Interactive Airmass Plotter",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8050,
        help="Port to run the server on (default: 8050)",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host to bind to (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Run in debug mode",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Don't open browser automatically",
    )

    args = parser.parse_args()

    # Import app and register callbacks
    from .gui.app import app
    from .gui.callbacks import register_callbacks

    register_callbacks(app)

    # Open browser after a short delay
    if not args.no_browser:
        url = f"http://{args.host}:{args.port}"
        Timer(1.5, lambda: webbrowser.open(url)).start()
        print(f"\nOpening browser at {url}")

    print(f"\nSkyCalc running at http://{args.host}:{args.port}")
    print("Press Ctrl+C to quit\n")

    # Run the server
    app.run(
        host=args.host,
        port=args.port,
        debug=args.debug,
    )


if __name__ == "__main__":
    main()
