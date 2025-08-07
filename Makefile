.PHONY: restart stop start test test-sms test-narrator test-claude test-all
.PHONY: daemon foreground claude debug-claude

claude:
	claude --mcp-config .mcp/mecris.json

debug-claude:
	claude --mcp-config .mcp/mecris.json --debug

restart: stop start

stop:
	-./scripts/shutdown_server.sh

start:
	./scripts/launch_server.sh

daemon: stop foreground

foreground:
	./scripts/launch_server.sh foreground

# Test targets
test-sms:
	@echo "🧪 Running SMS tests (mocked - no real messages sent)"
	@source venv/bin/activate && python tests/test_sms_mock.py

test-narrator:
	@echo "🧠 Running narrator context tests"
	@source venv/bin/activate && python tests/test_narrator_simple.py

test-claude:
	@echo "🎭 Running Claude integration demo"
	@source venv/bin/activate && python tests/test_claude_integration_demo.py

test-mecris:
	@echo "🔧 Running full Mecris system tests"
	@source venv/bin/activate && python -m tests.test_mecris

test: test-sms test-narrator
	@echo "✅ Core tests complete"

test-all: test-sms test-narrator test-claude test-mecris
	@echo "🎉 All tests complete"
