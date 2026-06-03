/** Maps common resume MIME types to their canonical file extension. */
export const MIME_TO_EXT: Record<string, string> = {
  "application/pdf": "pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
  "application/msword": "doc",
};

/** Returns the file extension for a MIME type, or `fallback` (default `"bin"`) if unknown. */
export function mimeToExt(mime: string, fallback = "bin"): string {
  return MIME_TO_EXT[mime] ?? fallback;
}
