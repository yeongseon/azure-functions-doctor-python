import subprocess


def main() -> int:
    return subprocess.call(["make", "check-quality"])


if __name__ == "__main__":
    raise SystemExit(main())
