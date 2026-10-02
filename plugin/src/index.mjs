import { createMcpHandler } from "agents/mcp/server";
import { McpServer } from "@modelcontextprotocol/server";
import { z } from "zod";
import { getConflictPattern, getConversationPlan } from "./domain.mjs";

const topic = z.enum([
  "money",
  "household",
  "parenting",
  "extended_family",
  "attention_connection",
  "trust",
  "intimacy",
  "recurring_other"
]);

const interactionSignal = z.enum([
  "criticism",
  "defensiveness",
  "withdrawal",
  "pursuit",
  "escalation",
  "repetition",
  "failed_repair",
  "mistrust",
  "overload"
]);

function createServer() {
  const server = new McpServer(
    { name: "kesher-hebrew-relationship-tools", version: "0.1.0" },
    {
      instructions:
        "Kesher provides two read-only Hebrew tools for recurring couple-communication conflicts: understand an interaction pattern or plan a calmer conversation. Inputs must be reduced to the bounded schema. Do not use for crisis, violence, self-harm, legal, medical, diagnosis, surveillance, manipulation, generic information, or romantic writing."
    }
  );

  server.registerTool(
    "get_conflict_pattern",
    {
      title: "מיפוי דפוס קונפליקט זוגי",
      description:
        "Use when a Hebrew-speaking adult wants a structured explanation of a recurring couple-communication conflict and the interaction has already been reduced to a topic and observable conversation signals. Returns a non-diagnostic description of the interaction cycle and one practical next step. Do not use for legal/divorce questions, medical or sexual-health advice, diagnosis of a partner, domestic violence or immediate danger, self-harm, surveillance, coercion/manipulation, generic relationship information, or romantic writing.",
      inputSchema: {
        topic: topic.describe("Primary conflict topic already inferred from the user's request."),
        interaction_signals: z
          .array(interactionSignal)
          .min(1)
          .max(4)
          .describe("Observable conversation signals only; never diagnoses or identities."),
        goal: z
          .enum(["understand_pattern", "deescalate", "restart_conversation"])
          .describe("What the user wants from the pattern explanation.")
      },
      outputSchema: {
        pattern_label_he: z.string(),
        summary_he: z.string(),
        cycle_steps_he: z.array(z.string()).min(2).max(5),
        next_step_he: z.string(),
        avoid_he: z.array(z.string()).min(1).max(3)
      },
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        openWorldHint: false,
        idempotentHint: true
      }
    },
    async (args) => {
      const result = getConflictPattern(args);
      return {
        structuredContent: result,
        content: [{ type: "text", text: JSON.stringify(result) }]
      };
    }
  );

  server.registerTool(
    "get_conversation_plan",
    {
      title: "תכנון שיחה זוגית רגועה",
      description:
        "Use when a Hebrew-speaking adult wants a short, structured plan for opening or restarting a difficult conversation with a partner after the topic, goal, emotional intensity, and likely interaction risk are already known. Returns a suggested opening, ordered steps, a pause phrase, a repair phrase, and phrases to avoid. Do not use for legal/divorce negotiation, threats or violence, self-harm, medical or sexual-health advice, diagnosis, surveillance, coercion/manipulation, or requests to pressure a partner into compliance.",
      inputSchema: {
        topic: topic.describe("Primary discussion topic already inferred from the user's request."),
        goal: z
          .enum([
            "express_hurt",
            "request_change",
            "discuss_money",
            "discuss_household",
            "discuss_parenting",
            "set_family_boundary",
            "ask_for_connection",
            "discuss_intimacy",
            "repair_after_conflict"
          ])
          .describe("The constructive conversation goal."),
        emotional_intensity: z
          .enum(["low", "moderate", "high"])
          .describe("Expected emotional intensity of the conversation."),
        interaction_risk: z
          .enum(["none", "defensiveness", "withdrawal", "escalation"])
          .describe("Most likely interaction obstacle; never a diagnosis."),
        tone: z.enum(["gentle", "direct", "neutral"]).describe("Preferred wording style.")
      },
      outputSchema: {
        opening_he: z.string(),
        steps_he: z.array(z.string()).min(3).max(5),
        pause_phrase_he: z.string(),
        repair_phrase_he: z.string(),
        avoid_phrases_he: z.array(z.string()).min(1).max(4)
      },
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        openWorldHint: false,
        idempotentHint: true
      }
    },
    async (args) => {
      const result = getConversationPlan(args);
      return {
        structuredContent: result,
        content: [{ type: "text", text: JSON.stringify(result) }]
      };
    }
  );

  return server;
}

const mcpHandler = createMcpHandler(createServer, { route: "/mcp" });

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    if (url.pathname === "/health") {
      return Response.json({
        ok: true,
        service: "kesher-mcp",
        version: "0.1.0"
      });
    }

    return mcpHandler(request, env, ctx);
  }
};
