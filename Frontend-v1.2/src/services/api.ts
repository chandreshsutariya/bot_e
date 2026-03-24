// Mandatory API key — must match BACKEND_API_KEY on the server
export const BACKEND_API_KEY = import.meta.env.VITE_BACKEND_API_KEY || "playage-bo-secret-2024";
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

/**
 * Derive a stable browser fingerprint using Web Crypto SHA-256.
 */
export async function computeFingerprint(): Promise<string> {
  const signals = [
    navigator.userAgent,
    navigator.language,
    `${screen.width}x${screen.height}x${screen.colorDepth}`,
    Intl.DateTimeFormat().resolvedOptions().timeZone,
    String(navigator.hardwareConcurrency ?? 0),
    navigator.platform,
    navigator.vendor ?? "",
  ].join("||");

  const encoded = new TextEncoder().encode(signals);
  const hashBuf = await crypto.subtle.digest("SHA-256", encoded);
  const hashArr = Array.from(new Uint8Array(hashBuf));
  return (
    "fp-" +
    hashArr
      .slice(0, 12)
      .map((b) => b.toString(16).padStart(2, "0"))
      .join("")
  );
}

export interface ParsedReference {
  index: number;
  title: string;
  url: string;
}

export function isVideoUrl(url: string): boolean {
  return /\.(mp4|webm|ogg|mov|avi)(\?.*)?$/i.test(url);
}

export function parseReferences(raw: string): ParsedReference[] {
  if (!raw || !raw.trim()) return [];

  const refs: ParsedReference[] = [];
  const pattern = /(\d+)\.\s+(.+?)\n\s+(https?:\/\/[^\s]+)/g;
  let match: RegExpExecArray | null;

  while ((match = pattern.exec(raw)) !== null) {
    refs.push({
      index: parseInt(match[1], 10),
      title: match[2].trim(),
      url: match[3].trim(),
    });
  }
  return refs;
}

export interface Message {
  id: string;
  text: string;
  sender: "user" | "bot";
  timestamp: Date;
  mediaUrls?: string[];
  videoUrls?: string[];
  references?: ParsedReference[];
  followUpQuestions?: string[];
  reaction?: string;
}
