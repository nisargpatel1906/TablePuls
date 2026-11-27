export function previewBulkCodes(
  prefix: string,
  startNumber: number,
  count: number,
  zeroPad: number,
): string[] {
  const cleanPrefix = prefix.trim().toUpperCase();
  if (!cleanPrefix || count < 1) return [];
  const res: string[] = [];
  const cap = Math.min(count, 50);
  for (let i = 0; i < cap; i += 1) {
    const numStr = String(startNumber + i).padStart(Math.max(1, zeroPad), "0");
    res.push(`${cleanPrefix}${numStr}`);
  }
  return res;
}
