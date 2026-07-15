/**
 * Mecris <-> Pi Bridge Extension
 * =================================================================
 * Brings the Mecris MCP server (the "Local Den" Python backend) into the
 * Pi coding agent as native Pi tools, so you can get a Mecris status update
 * "in the normal way" regardless of which harness you're driving.
 *
 * Parity target: the harnesses in .claude/, .gemini/, ~/.gemini/antigravity-cli/,
 * and the native py_harness/ all spawn the Mecris MCP server over stdio and
 * expose its tools. This extension does the same for Pi.
 *
 * Design notes (see also docs/PI_HARNESS_ROADMAP.md):
 *  - Spawns `mcp_stdio_server.py` (scheduler + stdio, NO port-8080 HTTP bridge)
 *    to match the native py_harness and avoid the uvicorn 8080 port conflict
 *    that `mcp_server.py --stdio` causes when another instance is running.
 *  - Registers every MCP tool but keeps only a small read-only "core" set
 *    active at startup, mirroring py_harness's filter_core_tools() lazy-loading
 *    for token efficiency. A `mecris_load_tools` loader activates the rest.
 *  - Converts MCP JSON-Schema tool inputs into TypeBox schemas so Pi can
 *    validate arguments the same way it validates its built-in tools.
 */

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type, type TSchema } from "typebox";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
import { existsSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

const HERE = dirname(fileURLToPath(import.meta.url));

/** Repo root: <repo>/.pi/extensions/mecris/index.ts -> up 3 levels. */
function resolveMecrisHome(): string {
  const fromEnv = process.env.MECRIS_HOME;
  if (fromEnv && existsSync(fromEnv)) return resolve(fromEnv);
  return resolve(HERE, "..", "..", "..");
}

const MECRIS_HOME = resolveMecrisHome();

/** Prefer the repo venv python for identical deps to the native harness. */
function resolvePython(): string {
  const fromEnv = process.env.MECRIS_PYTHON;
  if (fromEnv) return fromEnv;
  const venv = join(MECRIS_HOME, ".venv", "bin", "python");
  if (existsSync(venv)) return venv;
  return "python3";
}

const STDIO_SCRIPT =
  process.env.MECRIS_STDIO_SCRIPT || join(MECRIS_HOME, "mcp_stdio_server.py");

/**
 * Core tools kept active at startup. py_harness ships only get_narrator_context;
 * on a large Pi model we can afford a slightly richer read-only status set while
 * still deferring the 25+ write/admin tools behind the loader.
 */
const DEFAULT_CORE_TOOLS = [
  "get_narrator_context",
  "get_beeminder_status",
  "get_budget_status",
  "get_daily_aggregate_status",
  "get_system_health",
];

function coreToolSet(): Set<string> {
  const override = process.env.MECRIS_CORE_TOOLS;
  if (override && override.trim()) {
    return new Set(
      override
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean),
    );
  }
  return new Set(DEFAULT_CORE_TOOLS);
}

const TOOL_PREFIX = "mecris_"; // avoid collisions with Pi built-ins / github MCP
const LOADER_TOOL = "mecris_load_tools";
const STATUS_COMMAND = "mecris";

// ---------------------------------------------------------------------------
// JSON Schema -> TypeBox conversion
// ---------------------------------------------------------------------------

type JsonSchema = Record<string, any>;

function optsFrom(schema: JsonSchema): Record<string, unknown> {
  const o: Record<string, unknown> = {};
  if (typeof schema.description === "string") o.description = schema.description;
  // Skip null defaults: pydantic emits default:null for Optional[...] params, but a
  // null default on a typed (string/int) schema can trip strict validation.
  if (schema.default !== undefined && schema.default !== null) o.default = schema.default;
  if (schema.minimum !== undefined) o.minimum = schema.minimum;
  if (schema.maximum !== undefined) o.maximum = schema.maximum;
  if (Array.isArray(schema.enum)) o.enum = schema.enum;
  return o;
}

function toTypeBox(schema: JsonSchema | undefined): TSchema {
  if (!schema || typeof schema !== "object") return Type.Any();

  // Union / anyOf style — fall back to Any to stay permissive.
  if (schema.anyOf || schema.oneOf || schema.allOf) return Type.Any();

  const opts = optsFrom(schema);

  // MCP/pydantic frequently emits ["string", "null"] for Optional[...].
  const t = Array.isArray(schema.type)
    ? schema.type.find((x: string) => x !== "null") ?? "string"
    : schema.type;

  switch (t) {
    case "string":
      return Type.String(opts);
    case "integer":
      return Type.Integer(opts);
    case "number":
      return Type.Number(opts);
    case "boolean":
      return Type.Boolean(opts);
    case "array":
      return Type.Array(toTypeBox(schema.items), opts);
    case "object":
      return objectToTypeBox(schema);
    default:
      return Type.Any();
  }
}

function objectToTypeBox(schema: JsonSchema): TSchema {
  const properties: Record<string, TSchema> = {};
  const required = new Set<string>(
    Array.isArray(schema.required) ? schema.required : [],
  );
  const props = schema.properties ?? {};
  for (const [key, raw] of Object.entries<JsonSchema>(props)) {
    const inner = toTypeBox(raw);
    properties[key] = required.has(key) ? inner : Type.Optional(inner);
  }
  return Type.Object(properties, { additionalProperties: false });
}

// ---------------------------------------------------------------------------
// MCP result -> Pi tool result
// ---------------------------------------------------------------------------

function renderMcpContent(result: any): { text: string; isError: boolean } {
  const isError = Boolean(result?.isError);
  const parts: string[] = [];
  const content = Array.isArray(result?.content) ? result.content : [];
  for (const item of content) {
    if (item?.type === "text" && typeof item.text === "string") {
      parts.push(item.text);
    } else if (item?.type === "resource" && item.resource?.text) {
      parts.push(String(item.resource.text));
    } else {
      parts.push(JSON.stringify(item));
    }
  }
  if (parts.length === 0 && result?.structuredContent) {
    parts.push(JSON.stringify(result.structuredContent, null, 2));
  }
  return { text: parts.join("\n") || "(empty result)", isError };
}

// ---------------------------------------------------------------------------
// Extension
// ---------------------------------------------------------------------------

export default async function mecrisBridge(pi: ExtensionAPI) {
  let client: Client | null = null;
  let transport: StdioClientTransport | null = null;
  const registeredTools = new Set<string>();
  const core = coreToolSet();

  async function connect(): Promise<{ ok: boolean; error?: string }> {
    if (!existsSync(STDIO_SCRIPT)) {
      return { ok: false, error: `Mecris stdio script not found: ${STDIO_SCRIPT}` };
    }
    try {
      transport = new StdioClientTransport({
        command: resolvePython(),
        args: [STDIO_SCRIPT],
        cwd: MECRIS_HOME,
        env: {
          ...(process.env as Record<string, string>),
          PYTHONPATH: MECRIS_HOME,
        },
        stderr: "ignore",
      });
      client = new Client(
        { name: "pi-mecris-bridge", version: "0.0.1" },
        { capabilities: {} },
      );
      await client.connect(transport);
      return { ok: true };
    } catch (err) {
      return { ok: false, error: String(err) };
    }
  }

  async function registerTools(): Promise<number> {
    if (!client) return 0;
    const { tools } = await client.listTools();
    let count = 0;
    for (const tool of tools) {
      const piName = tool.name.startsWith(TOOL_PREFIX)
        ? tool.name
        : `${TOOL_PREFIX}${tool.name}`;
      if (registeredTools.has(piName)) continue;

      const parameters = objectToTypeBox(tool.inputSchema ?? { type: "object" });
      const upstreamName = tool.name;

      pi.registerTool({
        name: piName,
        label: `Mecris: ${upstreamName}`,
        description: tool.description || `Mecris tool ${upstreamName}`,
        parameters,
        async execute(_toolCallId, params) {
          if (!client) {
            return {
              content: [
                { type: "text", text: "Mecris MCP server is not connected." },
              ],
              details: { tool: upstreamName, connected: false },
              isError: true,
            };
          }
          try {
            const result = await client.callTool({
              name: upstreamName,
              arguments: (params ?? {}) as Record<string, unknown>,
            });
            const { text, isError } = renderMcpContent(result);
            return {
              content: [{ type: "text", text }],
              details: { tool: upstreamName },
              isError,
            };
          } catch (err) {
            return {
              content: [
                { type: "text", text: `Mecris tool ${upstreamName} failed: ${err}` },
              ],
              details: { tool: upstreamName },
              isError: true,
            };
          }
        },
      });
      registeredTools.add(piName);
      count++;
    }
    return count;
  }

  /**
   * Apply lazy-loading: keep only the core status set (+ loader + existing
   * actives) enabled. Uses runtime action methods, so it must run at/after
   * session_start, never during the extension factory load.
   */
  function applyLazyLoading(): void {
    const active = pi.getActiveTools();
    const coreActive = [...registeredTools].filter((name) =>
      core.has(name.replace(TOOL_PREFIX, "")),
    );
    const keep = new Set([...active, ...coreActive, LOADER_TOOL]);
    for (const name of registeredTools) {
      if (!coreActive.includes(name)) keep.delete(name);
    }
    pi.setActiveTools([...keep]);
  }

  // Loader tool: activates deferred Mecris tools on demand (parity w/ lazy load).
  pi.registerTool({
    name: LOADER_TOOL,
    label: "Mecris: Load Tools",
    description:
      "Search for and activate additional Mecris accountability tools (budget, " +
      "goals, language, scheduler, notifications, data export) that are not " +
      "active by default. Pass a keyword like 'beeminder', 'budget', 'language', " +
      "'notify', or 'all' to activate everything.",
    promptSnippet:
      "Activate additional Mecris tools when a task needs a capability not in the active set",
    promptGuidelines: [
      `Use ${LOADER_TOOL} when the user asks for a Mecris action (logging usage, ` +
        `adjusting goals, language levers, notifications) whose tool is not active.`,
    ],
    parameters: Type.Object({
      query: Type.String({
        description: "Capability keyword, upstream tool name, or 'all'",
      }),
    }),
    async execute(_toolCallId, params) {
      const query = (params.query ?? "").toString().toLowerCase().trim();
      const all = pi
        .getAllTools()
        .filter((t) => t.name.startsWith(TOOL_PREFIX) && t.name !== LOADER_TOOL);
      const matches =
        query === "all" || query === "*"
          ? all
          : all.filter((t) =>
              `${t.name} ${t.description}`.toLowerCase().includes(query),
            );
      if (matches.length === 0) {
        return {
          content: [
            { type: "text", text: `No Mecris tools matched "${query}".` },
          ],
          details: { matches: [] },
        };
      }
      const activeNow = pi.getActiveTools();
      const added = matches
        .map((t) => t.name)
        .filter((n) => !activeNow.includes(n));
      pi.setActiveTools([...new Set([...activeNow, ...added])]);
      return {
        content: [
          {
            type: "text",
            text:
              added.length > 0
                ? `Activated Mecris tools: ${added.join(", ")}`
                : `Already active: ${matches.map((t) => t.name).join(", ")}`,
          },
        ],
        details: { added },
      };
    },
  });

  // /mecris — get a status update "in the normal way".
  pi.registerCommand(STATUS_COMMAND, {
    description: "Ask Mecris for a personal accountability status update",
    handler: async (args, ctx) => {
      if (!client) {
        ctx.ui.notify("Mecris is not connected. Try /mecris-reconnect.", "warning");
        return;
      }
      const focus = args?.trim();
      const prompt = focus
        ? `Give me my Mecris status, focusing on: ${focus}. Call get_narrator_context first.`
        : "Give me my Mecris status. Call mecris_get_narrator_context first, then summarize urgent goals, runway, and budget.";
      pi.sendUserMessage(prompt);
    },
  });

  // /mecris-reconnect — restart the bridge without a full /reload.
  pi.registerCommand("mecris-reconnect", {
    description: "Reconnect the Mecris MCP bridge",
    handler: async (_args, ctx) => {
      await shutdown();
      const { ok, error } = await connect();
      if (!ok) {
        ctx.ui.notify(`Mecris reconnect failed: ${error}`, "error");
        return;
      }
      const n = await registerTools();
      applyLazyLoading();
      ctx.ui.notify(`Mecris reconnected (${n} new tools).`, "info");
    },
  });

  async function shutdown() {
    try {
      await client?.close();
    } catch {
      /* ignore */
    }
    try {
      await transport?.close();
    } catch {
      /* ignore */
    }
    client = null;
    transport = null;
  }

  pi.on("session_shutdown", async () => {
    await shutdown();
  });

  // Connect during async factory so tools exist before startup completes.
  // NOTE: registerTool() is load-safe, but getActiveTools()/setActiveTools()
  // are runtime action methods and must wait for session_start.
  const { ok, error } = await connect();
  if (!ok) {
    // Don't crash Pi — surface the problem and let /mecris-reconnect retry.
    pi.on("session_start", (_e, ctx) => {
      ctx.ui.notify(`Mecris bridge offline: ${error}`, "warning");
    });
    return;
  }
  const registered = await registerTools();
  pi.on("session_start", (_e, ctx) => {
    applyLazyLoading();
    ctx.ui.notify(
      `Mecris bridge online: ${registered} tools (${core.size} active, rest via ${LOADER_TOOL}).`,
      "info",
    );
  });
}
