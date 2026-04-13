import argparse
import sys
import asyncio
import json
import logging
import os
import signal
from typing import Optional
from dotenv import load_dotenv
from services.credentials_manager import credentials_manager

# Load environment variables from .env if present
load_dotenv()

def handle_termination(sig, frame):
    print(f"\n👋 Received signal {sig}. Exiting...")
    os._exit(130)

def main():
    # Set up signal handlers for graceful exit
    signal.signal(signal.SIGINT, handle_termination)
    signal.signal(signal.SIGTERM, handle_termination)

    _actual_main()

def setup_logging(verbose: bool):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s: %(message)s")
    
    # Silence third-party loggers that leak credentials in URLs
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

def resolve_user_id(args):
    """Resolve user ID from args or credentials manager."""
    user_id = credentials_manager.resolve_user_id(args.user_id)
    if not user_id:
        print("❌ Authentication Required.")
        print("Please run `mecris login` to authenticate your session.")
        sys.exit(1)
    
    # Familiar ID is mostly for display/logging if available
    return user_id

async def try_token_refresh() -> bool:
    """Attempt a silent token refresh using the stored refresh_token.

    Returns True if the session was refreshed or is still valid; False if the
    caller should fall through to the full browser login flow.
    """
    import time
    import jwt
    from services.auth_utils import exchange_refresh_token

    creds = credentials_manager.load_credentials()
    refresh_token = creds.get("refresh_token")
    if not refresh_token:
        return False

    # Check if the current access token is still valid.
    access_token = creds.get("access_token")
    if access_token:
        try:
            decoded = jwt.decode(access_token, options={"verify_signature": False})
            if decoded.get("exp", 0) > time.time() + 1800:
                print(f"✅ Already logged in as: {creds.get('familiar_id', creds.get('user_id'))}")
                return True
        except Exception:
            pass

    print("Access token expired. Attempting silent refresh...")
    try:
        tokens = await asyncio.to_thread(exchange_refresh_token, refresh_token)
        if "access_token" not in tokens:
            return False
        creds["access_token"] = tokens.get("access_token")
        if tokens.get("refresh_token"):
            creds["refresh_token"] = tokens.get("refresh_token")
        if tokens.get("id_token"):
            creds["id_token"] = tokens.get("id_token")
        if tokens.get("expires_in"):
            creds["expires_in"] = tokens.get("expires_in")
        credentials_manager.save_credentials(creds)
        print(f"✅ Token refreshed. Logged in as: {creds.get('familiar_id', creds.get('user_id'))}")
        return True
    except Exception as e:
        print(f"⚠️ Silent refresh failed ({e}). Falling back to browser login...")
        return False

async def run_login(args):
    """Initiate the OIDC login flow via PKCE and loopback server."""
    from services.auth_utils import generate_pkce_pair, generate_state, build_auth_url, get_redirect_port
    from services.auth_server import start_loopback_server, wait_for_code
    import webbrowser

    if await try_token_refresh():
        return

    print("Initiating login flow via Pocket ID...")
    
    verifier, challenge = generate_pkce_pair()
    state = generate_state()
    
    # 0. Get Port
    port_preference = get_redirect_port()
    
    # 1. Start loopback server
    server = None
    try:
        server_info = start_loopback_server(port=port_preference)
        port = server_info["port"]
        server = server_info["server"]
        if port_preference != 0 and port != port_preference:
            print(f"⚠️ Could not bind to preferred port {port_preference}. Using port {port} instead.")
    except Exception as e:
        print(f"❌ Failed to start local loopback server: {e}")
        return

    # 2. Build Auth URL
    auth_url = build_auth_url(challenge, state, port)
    
    print(f"\nOpening your browser to authenticate...")
    print(f"URL: {auth_url}")
    print("\nWaiting for redirect from Pocket ID...")
    
    # 3. Open Browser
    webbrowser.open(auth_url)
    
    # 4. Wait for code
    try:
        # We wrap wait_for_code in a thread but we keep a reference to server to shut it down if we interrupt.
        code = await asyncio.to_thread(wait_for_code, server, state, timeout=300)
    except (KeyboardInterrupt, asyncio.CancelledError):
        print("\n\nLogin process interrupted by user.")
        if server:
            server.shutdown()
        return
    except Exception as e:
        print(f"❌ An error occurred during login: {e}")
        if server:
            server.shutdown()
        return
    
    if not code:
        print("❌ Login failed: Timed out or invalid state received.")
        return

    print(f"✅ Authorization code received.")
    
    # 5. Token Exchange
    try:
        from services.auth_utils import exchange_code_for_tokens
        print("Exchanging code for tokens...")
        tokens = await asyncio.to_thread(exchange_code_for_tokens, code, verifier, port)
        
        if "access_token" not in tokens:
            print(f"❌ Login failed: No access token received. Response: {tokens}")
            return
            
        # 6. Extract User ID (sub)
        import jwt
        token = tokens.get("id_token") or tokens.get("access_token")
        decoded = jwt.decode(token, options={"verify_signature": False})
        user_id = decoded.get("sub")
        
        if not user_id:
            print("❌ Login failed: Could determine user ID from token.")
            return

        # 7. Resolve Familiar ID from Neon if possible
        familiar_id = user_id
        from services.neon_sync_checker import NeonSyncChecker
        try:
            checker = NeonSyncChecker()
            if checker.db_url:
                import psycopg2
                with psycopg2.connect(checker.db_url) as conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT familiar_id FROM users WHERE pocket_id_sub = %s", (user_id,))
                        row = cur.fetchone()
                        if row and row[0]:
                            familiar_id = row[0]
        except Exception:
            pass # Fallback to UUID is fine
            
        # 8. Save Credentials
        creds_data = {
            "user_id": user_id,
            "familiar_id": familiar_id,
            "access_token": tokens.get("access_token"),
            "refresh_token": tokens.get("refresh_token"),
            "id_token": tokens.get("id_token"),
            "expires_in": tokens.get("expires_in")
        }
        credentials_manager.save_credentials(creds_data)
        
        print(f"\n✅ Login Successful!")
        print(f"Logged in as: {familiar_id} ({user_id})")
        print("You can now use Mecris CLI and MCP server tools.")
        
    except Exception as e:
        print(f"❌ Login failed during token exchange: {e}")

async def run_nag_eval(args):
    """Evaluate the reminder heuristics without triggering a send."""
    from mcp_server import check_reminder_needed
    user_id = resolve_user_id(args)
    
    print(f"Evaluating nagging heuristics for user_id='{user_id}'...")
    result = await check_reminder_needed(user_id)
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
    user_id = resolve_user_id(args)
    
    if args.force:
        print(f"FORCING a reminder evaluation and send for user_id='{user_id}'...")
        check_result = await check_reminder_needed(user_id)
        if not check_result.get("should_send"):
            print("⚠️ The heuristic didn't want to send anything. We are forcing a test payload.")
            check_result = {
                "type": "forced_test",
                "message": "This is a forced test message from the Mecris CLI.",
                "should_send": True
            }
            print(f"Payload: {json.dumps(check_result, indent=2)}")
        
        send_result = await send_reminder_message(check_result, user_id)
        print(f"Send result: {json.dumps(send_result, indent=2)}")
    else:
        print(f"Triggering normal reminder check for user_id='{user_id}'...")
        result = await trigger_reminder_check(user_id)
        print(json.dumps(result, indent=2))

def run_presence(args):
    """Check for or take the presence lock."""
    from ghost.presence import acquire_lock, release_lock, check_presence
    import os

    lock_path = os.path.join(os.getcwd(), "presence.lock")

    if args.action == "take":
        acquire_lock(lock_path)
        print("✅ Presence lock taken.")
        return 0

    if args.action == "release":
        removed = release_lock(lock_path)
        if removed:
            print("✅ Presence lock released.")
        else:
            print("ℹ️ No presence lock to release.")
        return 0

    # Default: check
    status = check_presence(lock_path)
    if not status.lock_exists:
        print("✅ NO human presence detected (no lock file).")
        return 0

    if status.human_present:
        print(f"⚠️ Human presence detected ({int(status.age_seconds)}s ago).")
        return 1
    else:
        print(f"✅ Stale presence lock found ({int(status.age_seconds)}s old). Assuming human is gone.")
        return 0

async def run_internal_presence(args):
    """Report presence status to Neon."""
    from ghost.presence import get_neon_store, StatusType
    user_id = resolve_user_id(args)
    store = get_neon_store()
    if not store:
        print("❌ Neon DB not available. Cannot report presence.")
        sys.exit(1)
    
    status = StatusType.ACTIVE_GHOST if args.ghost else StatusType.ACTIVE_HUMAN
    try:
        record = store.upsert(user_id, status, source="cli")
        print(f"✅ Presence reported as {status.value} for user {user_id}.")
        print(f"   Last Active: {record.last_active}")
    except Exception as e:
        print(f"❌ Failed to report presence: {e}")
        sys.exit(1)

def _actual_main():
    parser = argparse.ArgumentParser(description="Mecris CLI - The Ground Truth")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")
    parser.add_argument("--user-id", type=str, default=None, help="Target user ID (overrides local credentials)")
    
    subparsers = parser.add_subparsers(dest="command", help="Sub-commands")
    
    # --- Login Subcommand ---
    login_parser = subparsers.add_parser("login", help="Log in to Mecris via Pocket ID")
    
    # --- Presence Subcommand ---
    presence_parser = subparsers.add_parser("presence", help="Manage human presence lock for ghost sessions")
    presence_parser.add_argument("action", choices=["check", "take", "release"], default="check", nargs="?", help="Action to perform")
    
    # --- Internal Subcommands ---
    internal_parser = subparsers.add_parser("internal", help="Internal system maintenance handles")
    internal_subparsers = internal_parser.add_subparsers(dest="internal_command")
    
    int_presence_parser = internal_subparsers.add_parser("presence", help="Report presence to the global store")
    int_presence_parser.add_argument("--ghost", action="store_true", help="Report as ghost presence instead of human")

    # --- Nag Subcommands ---
    nag_parser = subparsers.add_parser("nag", help="Autonomous Nagging System controls")
    nag_subparsers = nag_parser.add_subparsers(dest="nag_command")
    
    eval_parser = nag_subparsers.add_parser("eval", help="Evaluate the current heuristics without sending anything")
    
    trigger_parser = nag_subparsers.add_parser("trigger", help="Evaluate and send if needed")
    trigger_parser.add_argument("--force", action="store_true", help="Force send even if heuristic says no (dangerous)")
    
    args = parser.parse_args()
    
    setup_logging(args.verbose)
    
    if args.command == "login":
        asyncio.run(run_login(args))
    elif args.command == "presence":
        sys.exit(run_presence(args))
    elif args.command == "internal":
        if args.internal_command == "presence":
            asyncio.run(run_internal_presence(args))
        else:
            internal_parser.print_help()
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
