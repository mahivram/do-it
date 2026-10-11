import argparse

from automation.web import serve


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local Do It agent UI.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8000, type=int)
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Restart the Python server when project Python files change.",
    )
    args = parser.parse_args()
    serve(host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
