/** "1 call", "2 calls" — counts on screen always agree with their noun. */
export function plural(n: number, one: string, many = `${one}s`): string {
  return `${n} ${n === 1 ? one : many}`;
}
