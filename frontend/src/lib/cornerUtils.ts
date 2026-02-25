/** Parse corner number from corner ID string like "T5" -> 5 */
export function parseCornerNumber(cornerId: string): number | null {
  const match = cornerId.match(/\d+/);
  return match ? parseInt(match[0], 10) : null;
}
