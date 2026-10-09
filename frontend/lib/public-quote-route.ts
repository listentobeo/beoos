export function isPublicQuoteRequest(path: string[], method: string): boolean {
  if (path[0] !== "quotes" || !/^[A-Za-z0-9_-]{32,96}$/.test(path[1] ?? "")) return false;
  return (method === "GET" && path.length === 2)
    || (method === "POST" && path.length === 3 && path[2] === "accept");
}
