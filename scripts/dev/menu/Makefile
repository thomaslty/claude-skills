# App dev commands. A bare `make` lists every command with an example; `make menu` picks any of them from a menu.
# ENV=local (the default) runs docker-compose.yml with .env.local over .env; ENV=dev runs it with .env.dev.
#
# This is /dev:create-menu's example: a docker compose stack with a backend and a frontend service.
# Every target in it is replaced by the repo's own commands; keep the shape, the help block and menu:.

ENV ?= local
COMMAND  := $(firstword $(MAKECMDGOALS))
ARGS     := $(wordlist 2,$(words $(MAKECMDGOALS)),$(MAKECMDGOALS))
ARGWORDS := backend frontend env-file git-hook

.PHONY: help menu up down logs build clean setup $(ARGWORDS)
.DEFAULT_GOAL := help

define HELP
App dev commands (docker compose)

  make menu                       pick any command below from a menu instead of typing it

Run the stack
  make up                         build, then run; shows the logs
  make up DETACH=1                same, in the background
  make up BUILD=backend           build the backend only, then run; BUILD=frontend, or BUILD=none to build nothing
  make up ENV=dev                 the same with .env.dev
  make down                       stop the stack
  make logs                       follow the stack: the last 200 lines, then live
  make clean                      stop the stack, then delete .data/, after you type yes

Build
  make build                      backend, then frontend, never both at once
  make build backend              the backend image only
  make build frontend             the frontend image only

Setup, once after clone
  make setup                      both steps below
  make setup env-file             copy .env.example to .env, when there is no .env yet
  make setup git-hook             point git at the tracked hooks in .githooks/

  make help                       this list

ENV=local|dev (default local) · DETACH=1 · BUILD=backend|frontend|none

Examples
  First time after clone
    make setup
    make up DETACH=1
  Rebuild the backend only, then run in the background
    make up BUILD=backend DETACH=1
endef
export HELP

ifneq ($(filter $(COMMAND),$(ARGWORDS)),)
$(error "$(COMMAND)" goes after a command, like make build backend or make setup git-hook)
endif
ifneq ($(filter-out backend frontend none,$(BUILD)),)
$(error BUILD is backend, frontend or none, like make up BUILD=backend; leave it out to build both)
endif

ifeq ($(ENV),local)
COMPOSE := $(strip docker compose $(addprefix --env-file ,$(wildcard .env .env.local)))
else ifeq ($(ENV),dev)
COMPOSE := docker compose --env-file .env.dev
else
$(error ENV is local or dev, like make up ENV=dev)
endif

help:               # Every command with an example
	@echo "$$HELP"

menu:               # Pick any command from a menu (app_cli/) instead of typing it
	@command -v uv >/dev/null || { echo "make menu needs uv, like brew install uv"; exit 1; }
	@uv run --project app_cli app-menu

up:                 # Build, then run: attached so you see the logs, DETACH=1 for the background, BUILD= for one image or none
ifneq ($(BUILD),none)
	@$(MAKE) --no-print-directory build $(BUILD)
endif
	$(COMPOSE) up $(if $(filter 1 yes true,$(DETACH)),-d)

down:               # Stop the stack; .data/ stays
	$(COMPOSE) down

logs:               # Follow the stack: the last 200 lines, then live
	$(COMPOSE) logs -f --tail 200

build:              # One image, or both one after the other
	@for service in $(or $(filter backend frontend,$(ARGS)),backend frontend); do \
		$(COMPOSE) build $$service || exit 1; \
	done

clean:              # Stop the stack, then delete .data/, the files its containers keep; asks for yes first
	@printf 'make clean deletes .data/ and cannot be undone. Type yes: '; read answer; \
		test "$$answer" = yes || { echo "make clean: kept .data/"; exit 1; }
	$(COMPOSE) down
	rm -rf .data
	@echo "deleted .data/; the next make up starts empty"

setup:              # Once after clone: copy .env.example to .env, point git at .githooks/
ifneq ($(filter env-file,$(or $(filter env-file git-hook,$(ARGS)),env-file)),)
	@if [ -f .env ]; then echo ".env is there already; left as it is"; \
		else cp .env.example .env && echo "copied .env.example to .env; fill in the passwords"; fi
endif
ifneq ($(filter git-hook,$(or $(filter env-file git-hook,$(ARGS)),git-hook)),)
	git config core.hooksPath .githooks
endif

$(ARGWORDS):
	@:
