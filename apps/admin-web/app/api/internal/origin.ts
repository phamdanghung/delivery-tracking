/** Next may normalize nextUrl's hostname; compare the browser Origin with Host. */
export function sameOrigin(
  origin: string | null,
  protocol: string,
  host: string | null,
): boolean {
  return Boolean(host) && origin === `${protocol}//${host}`;
}
