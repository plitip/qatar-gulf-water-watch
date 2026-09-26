export function mean(arr) {
  return arr.reduce((a, b) => a + b, 0) / arr.length;
}

export function stddev(arr, m) {
  const v = arr.reduce((a, b) => a + (b - m) * (b - m), 0) / arr.length;
  return Math.sqrt(v);
}
