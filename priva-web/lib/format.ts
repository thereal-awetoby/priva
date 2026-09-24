export function timeAgo(iso: string): string {
    const diffSec = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
    if (diffSec < 60) return `${diffSec}s ago`;
    const diffMin = Math.floor(diffSec / 60);
    if (diffMin < 60) return `${diffMin}m ago`;
    const diffHr = Math.floor(diffMin / 60);
    if (diffHr < 24) return `${diffHr}h ago`;
    return `${Math.floor(diffHr / 24)}d ago`;
  }

export function formatActivityTime(value: unknown): { display: string; title?: string } {
  if (!value) return { display: "—" };
  const date = new Date(String(value));
  if (Number.isNaN(date.getTime())) return { display: "—" };

  const title = date.toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
  const ageMs = Date.now() - date.getTime();
  const display = ageMs > 24 * 60 * 60 * 1000
    ? date.toLocaleString(undefined, {
        month: "short",
        day: "numeric",
        hour: "numeric",
        minute: "2-digit",
      })
    : timeAgo(date.toISOString());

  return { display, title };
}
  
  export function cleanSymbol(symbol: string): string {
    return symbol.replace(/USDT$/, "");
  }