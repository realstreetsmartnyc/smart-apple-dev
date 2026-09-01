"""smart-apple-dev CLI entry point."""

import sys


def main():
    """Main entry point for smart-apple-dev."""
    from .app import cli
    cli()


if __name__ == "__main__":
    main()
