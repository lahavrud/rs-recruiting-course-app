import { mimeToExt } from "@/utils/mime";

export const RESUME_ALLOWED_EXTENSIONS = [".pdf", ".doc", ".docx"] as const;
export const RESUME_MAX_FILE_SIZE_MB = 10;
export const RESUME_MAX_FILE_SIZE_BYTES = RESUME_MAX_FILE_SIZE_MB * 1024 * 1024;

/** Slug from a candidate name, suitable for use in a filename. */
function slugifyCandidate(name: string): string {
  return name.trim().replace(/\s+/g, "-");
}

/**
 * Build a download filename for a resume: `{candidate-name}-resume.{ext}`.
 * Picks the extension from the MIME type when known, falling back to the
 * file-key's own extension, then to `bin` as a last resort.
 */
export function buildResumeDownloadName(
  candidateName: string,
  fileKey: string,
  mimeType: string,
): string {
  const keyExt = fileKey.includes(".") ? fileKey.split(".").pop() : undefined;
  const safeKeyExt =
    keyExt && /^[a-zA-Z0-9]{1,5}$/.test(keyExt) ? keyExt.toLowerCase() : undefined;
  const ext = mimeToExt(mimeType, safeKeyExt ?? "bin");
  return `${slugifyCandidate(candidateName)}-resume.${ext}`;
}

/** True when the file should render inline in an iframe (PDFs only). */
export function isInlinePreviewable(mimeType: string, fileKey: string): boolean {
  if (mimeType === "application/pdf") return true;
  if (fileKey.toLowerCase().endsWith(".pdf")) return true;
  return false;
}

/** True if the current device is iOS (Safari blocks `<a download>` on blob URLs). */
export function isIOS(): boolean {
  if (typeof navigator === "undefined") return false;
  return (
    /iPhone|iPad|iPod/.test(navigator.userAgent) ||
    (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1)
  );
}

/**
 * Trigger a download of a blob with the given filename. On iOS, falls back
 * to the Web Share API since `<a download>` on a blob URL is silently ignored.
 * Returns true if the download/share was initiated, false if neither worked
 * (caller should open the URL in a new tab as a last resort).
 */
export async function downloadOrShareBlob(
  blob: Blob,
  filename: string,
): Promise<boolean> {
  const mimeType = blob.type || "application/octet-stream";

  if (isIOS() && typeof navigator.canShare === "function") {
    const file = new File([blob], filename, { type: mimeType });
    if (navigator.canShare({ files: [file] })) {
      try {
        await navigator.share({ files: [file] });
        return true;
      } catch (err) {
        // User cancelled — counts as "handled", don't fall through to download
        if (err instanceof Error && err.name === "AbortError") return true;
      }
    }
  }

  const url = URL.createObjectURL(blob);
  try {
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    return true;
  } finally {
    // Browsers may need a moment to start the download before we revoke.
    setTimeout(() => URL.revokeObjectURL(url), 30_000);
  }
}
