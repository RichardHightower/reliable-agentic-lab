export function add(a, b) { return a + b; }
export function div(a, b) {
  if (b === 0) throw new Error("divide by zero");
  return a / b;
}
