"""smart-apple-dev CLI entry point."""

import sys

def main():
    """Main entry point for smart-apple-dev."""
    from .cli.app import cli
    cli()

if __name__ == "__main__":
    main()