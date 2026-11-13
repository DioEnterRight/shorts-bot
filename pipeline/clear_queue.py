"""THROW AWAY READY VIDEOS: marks every queued video as discarded and deletes its release,
so the bot makes fresh ones next run. Use it when you don't like what's waiting."""
from .common import load_history, log, run, save_history


def main():
    history = load_history()
    n = 0
    for v in history["videos"]:
        if v.get("status") == "queued":
            run(["gh", "release", "delete", v["tag"], "--yes", "--cleanup-tag"], check=False)
            v["status"] = "discarded"
            n += 1
    save_history(history)
    log(f"Discarded {n} ready video(s).")


if __name__ == "__main__":
    main()
