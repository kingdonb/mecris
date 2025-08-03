.PHONY: restart stop start

restart: stop start

stop:
	-./scripts/shutdown_server.sh

start:
	./scripts/launch_server.sh
