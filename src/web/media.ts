import { fileTypeFromBuffer } from "file-type";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

export type LoadedMedia = {
  buffer: Buffer;
  contentType: string | null;
  fileName: string | null;
  kind?: "image" | "audio" | "video" | "document";
};

export async function loadWebMedia(
  urlOrPath: string,
  options?: {
    maxBytes?: number;
    localRoots?: readonly string[];
    readFile?: (filePath: string) => Promise<Buffer>;
    sandboxValidated?: boolean;
  },
): Promise<LoadedMedia | undefined> {
  try {
    if (/^https?:\/\//i.test(urlOrPath)) {
      const res = await fetch(urlOrPath);
      if (!res.ok) {
        throw new Error(`${res.status} ${res.statusText}`);
      }
      const arrayBuffer = await res.arrayBuffer();
      const buffer = Buffer.from(arrayBuffer);
      if (options?.maxBytes && buffer.length > options.maxBytes) {
        throw new Error(`file too large (${buffer.length} bytes > ${options.maxBytes} bytes)`);
      }

      const type = await fileTypeFromBuffer(buffer);
      const mime = type?.mime ?? res.headers.get("content-type");
      let kind: "image" | "audio" | "video" | "document" = "document";
      if (mime?.startsWith("image/")) {
        kind = "image";
      } else if (mime?.startsWith("audio/")) {
        kind = "audio";
      } else if (mime?.startsWith("video/")) {
        kind = "video";
      }

      return {
        buffer,
        contentType: mime || null,
        fileName: path.basename(new URL(urlOrPath).pathname) || "download",
        kind,
      };
    }

    let filePath = urlOrPath;
    if (urlOrPath.startsWith("file://")) {
      filePath = fileURLToPath(urlOrPath);
    }

    if (options?.localRoots && !options.sandboxValidated) {
      const resolved = path.resolve(filePath);
      const allowed = options.localRoots.some((root) => resolved.startsWith(path.resolve(root)));
      if (!allowed) {
        throw new Error(`path not allowed: ${filePath}`);
      }
    }

    const readFile = options?.readFile ?? fs.readFile;
    const buffer = await readFile(filePath);

    if (options?.maxBytes && buffer.length > options.maxBytes) {
      throw new Error(`file too large (${buffer.length} bytes > ${options.maxBytes} bytes)`);
    }

    const type = await fileTypeFromBuffer(buffer);
    const mime = type?.mime ?? null;
    let kind: "image" | "audio" | "video" | "document" = "document";
    if (mime?.startsWith("image/")) {
      kind = "image";
    } else if (mime?.startsWith("audio/")) {
      kind = "audio";
    } else if (mime?.startsWith("video/")) {
      kind = "video";
    }

    return {
      buffer,
      contentType: mime,
      fileName: path.basename(filePath),
      kind,
    };
  } catch (err) {
    throw new Error(`Load failed: ${err instanceof Error ? err.message : String(err)}`, {
      cause: err,
    });
  }
}

export function getDefaultLocalRoots() {
  return [process.cwd()];
}
