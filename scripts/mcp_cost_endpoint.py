from flask import Flask, jsonify
from anthropic_cost_tracker import AnthropicCostTracker
import os

app = Flask(__name__)
cost_tracker = AnthropicCostTracker()

@app.route('/usage', methods=['GET'])
def get_usage():
    """
    Endpoint to retrieve Anthropic API usage and cost information
    """
    try:
        summary = cost_tracker.get_budget_summary()
        return jsonify(summary), 200
    except Exception as e:
        return jsonify({
            'error': str(e),
            'message': 'Unable to retrieve usage information'
        }), 500

if __name__ == '__main__':
    # Default to localhost and port 8000 if not specified
    host = os.environ.get('MCP_HOST', 'localhost')
    port = int(os.environ.get('MCP_PORT', 8000))
    app.run(host=host, port=port, debug=True)