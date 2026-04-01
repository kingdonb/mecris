import argparse
import sys
import asyncio
import json
import logging

# We import the required parts lazily to make the CLI fast, 
# but for the main entrypoint we set up the parser.

def setup_logging(verbose: bool):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s: %(message)s")
    
    # Silence third-party loggers that leak credentials in URLs
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

async def run_nag_eval(args):
    """Evaluate the reminder heuristics without triggering a send."""
    from mcp_server import check_reminder_needed
    
    print(f"Evaluating nagging heuristics for user_id='{args.user_id}'...")
    result = await check_reminder_needed(args.user_id)
    print("\n--- Heuristic Result ---")
    print(json.dumps(result, indent=2))

    if result.get("should_send"):
        tier = result.get("tier", "?")
        print(f"\n✅ A nag WOULD be triggered right now.  Tier: {tier}")
    else:
        print("\n❌ No nag would be sent.")

async def run_nag_trigger(args):
    """Evaluate and actually send the reminder if needed, or force it."""
    from mcp_server import trigger_reminder_check, send_reminder_message, check_reminder_needed
    
    if args.force:
        print(f"FORCING a reminder evaluation and send for user_id='{args.user_id}'...")
        # Since we are forcing, we bypass the "should_send" logic.
        # But we still need the data of what *would* have been sent.
        check_result = await check_reminder_needed(args.user_id)
        if not check_result.get("should_send"):
            print("⚠️ The heuristic didn't want to send anything. We are forcing a test payload.")
            check_result = {
                "type": "forced_test",
                "message": "This is a forced test message from the Mecris CLI.",
                "should_send": True
            }
            print(f"Payload: {json.dumps(check_result, indent=2)}")
        
        send_result = await send_reminder_message(check_result, args.user_id)
        print(f"Send result: {json.dumps(send_result, indent=2)}")
    else:
        print(f"Triggering normal reminder check for user_id='{args.user_id}'...")
        result = await trigger_reminder_check(args.user_id)
        print(json.dumps(result, indent=2))

def run_presence(args):
    """Check for or take the presence lock."""
    import os
    import time
    
    lock_path = os.path.join(os.getcwd(), "presence.lock")
    
    if args.action == "take":
        with open(lock_path, "w") as f:
            f.write(str(int(time.time())))
        print("✅ Presence lock taken.")
        return 0
    
    if args.action == "release":
        if os.path.exists(lock_path):
            os.remove(lock_path)
            print("✅ Presence lock released.")
        else:
            print("ℹ️ No presence lock to release.")
        return 0
    
    # Default: check
    if not os.path.exists(lock_path):
        print("✅ NO human presence detected (no lock file).")
        return 0
    
    # Check age
    mtime = os.path.getmtime(lock_path)
    age = time.time() - mtime
    
    if age < (30 * 60): # 30 minutes
        print(f"⚠️ Human presence detected ({int(age)}s ago).")
        return 1
    else:
        print(f"✅ Stale presence lock found ({int(age)}s old). Assuming human is gone.")
        return 0

def main():
    parser = argparse.ArgumentParser(description="Mecris CLI - The Ground Truth")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")
    parser.add_argument("--user-id", type=str, default=None, help="Target user ID (defaults to DEFAULT_USER_ID)")
    
    subparsers = parser.add_subparsers(dest="command", help="Sub-commands")
    
    # --- Presence Subcommand ---
    presence_parser = subparsers.add_parser("presence", help="Manage human presence lock for ghost sessions")
    presence_parser.add_argument("action", choices=["check", "take", "release"], default="check", nargs="?", help="Action to perform")
    
    # --- Nag Subcommands ---
    nag_parser = subparsers.add_parser("nag", help="Autonomous Nagging System controls")
    nag_subparsers = nag_parser.add_subparsers(dest="nag_command")
    
    eval_parser = nag_subparsers.add_parser("eval", help="Evaluate the current heuristics without sending anything")
    
    trigger_parser = nag_subparsers.add_parser("trigger", help="Evaluate and send if needed")
    trigger_parser.add_argument("--force", action="store_true", help="Force send even if heuristic says no (dangerous)")
    
    args = parser.parse_args()
    
    setup_logging(args.verbose)
    
    if args.command == "presence":
        sys.exit(run_presence(args))
    elif args.command == "nag":
        if args.nag_command == "eval":
            asyncio.run(run_nag_eval(args))
        elif args.nag_command == "trigger":
            asyncio.run(run_nag_trigger(args))
        else:
            nag_parser.print_help()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
