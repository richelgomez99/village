import { z } from "zod";

export const serverFrameSchema = z.discriminatedUnion("type", [
  z.object({ type: z.literal("snapshot") }).passthrough(),
  z.object({ type: z.literal("patch") }).passthrough(),
  z.object({ type: z.literal("event") }).passthrough(),
  z.object({ type: z.literal("control") }).passthrough(),
  z.object({ type: z.literal("prompt") }).passthrough(),
  z.object({ type: z.literal("result") }).passthrough(),
  z.object({ type: z.literal("pong") }).passthrough(),
  z.object({ type: z.literal("error") }).passthrough(),
  z.object({ type: z.literal("chat") }).passthrough()
]);

export type ServerFrame = z.infer<typeof serverFrameSchema>;

export interface ClientHello {
  type: "hello";
  contract_version: "1.1.0";
  village: string;
  member_token: string;
  last_rev?: number;
  client: "kit" | "control" | "scan_page" | "test";
}
