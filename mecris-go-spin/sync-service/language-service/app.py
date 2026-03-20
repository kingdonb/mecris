import json
from spin_sdk import http, postgres, variables
from spin_sdk.http import IncomingHandler, Request, Response

class IncomingHandler(IncomingHandler):
    def handle_request(self, request: Request) -> Response:
        db_url = variables.get("db_url")
        
        try:
            conn = postgres.open(db_url)
            # Fetch all language stats
            row_set = conn.query("SELECT language_name, current_reviews, tomorrow_reviews, next_7_days_reviews FROM language_stats", [])
            
            languages = []
            for row in row_set.rows:
                # Column order: language_name (0), current_reviews (1), tomorrow_reviews (2), next_7_days_reviews (3)
                languages.append({
                    "name": row[0],
                    "current": int(row[1]),
                    "tomorrow": int(row[2]),
                    "next_7_days": int(row[3])
                })
            
            return Response(
                200,
                {"content-type": "application/json"},
                bytes(json.dumps({"languages": languages}), "utf-8")
            )
        except Exception as e:
            return Response(
                500,
                {"content-type": "text/plain"},
                bytes(f"Error: {str(e)}", "utf-8")
            )
