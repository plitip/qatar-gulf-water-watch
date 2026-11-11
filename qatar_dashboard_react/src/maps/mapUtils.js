// Shared by the 2008 map and the recent-days map: the frames arrive as 2-bit classes packed
// three to a base64 character (see bloomwatch/gulf.py, encode_map_classes).

const ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_";
const CHAR_VALUE = Object.fromEntries([...ALPHABET].map((c, i) => [c, i]));
const CLASS_COLORS = ["--map-land", "--map-sea", "--map-above", "--map-flagged"];

export function decode(cells, count) {
  const classes = new Uint8Array(count);
  for (let i = 0; i < cells.length; i++) {
    const n = CHAR_VALUE[cells[i]];
    const at = i * 3;
    if (at < count) classes[at] = n >> 4;
    if (at + 1 < count) classes[at + 1] = (n >> 2) & 3;
    if (at + 2 < count) classes[at + 2] = n & 3;
  }
  return classes;
}

function cssColor(name) {
  const hex = getComputedStyle(document.documentElement).getPropertyValue(name).trim().replace("#", "");
  return [0, 2, 4].map((i) => parseInt(hex.slice(i, i + 2), 16));
}

// Paint one frame's classes onto a canvas sized cols x rows. Colours come from the CSS tokens.
export function drawClasses(canvas, classes, cols, rows) {
  const ctx = canvas.getContext("2d");
  const image = ctx.createImageData(cols, rows);
  const colors = CLASS_COLORS.map(cssColor);
  for (let i = 0; i < classes.length; i++) {
    const [r, g, b] = colors[classes[i]];
    image.data[i * 4] = r;
    image.data[i * 4 + 1] = g;
    image.data[i * 4 + 2] = b;
    image.data[i * 4 + 3] = 255;
  }
  ctx.putImageData(image, 0, 0);
}

// Grid values are pixel centres; the image spans half a pixel beyond them on every side.
export function placeOnMap(point, grid) {
  const latStep = (grid.north - grid.south) / (grid.rows - 1);
  const lonStep = (grid.east - grid.west) / (grid.cols - 1);
  return {
    left: `${((point.lon - (grid.west - lonStep / 2)) / (grid.cols * lonStep)) * 100}%`,
    top: `${((grid.north + latStep / 2 - point.lat) / (grid.rows * latStep)) * 100}%`,
  };
}

// Width over height of the map once longitude is shrunk to true distance at mid-latitude.
export function mapAspect(grid) {
  const midLat = grid ? (grid.north + grid.south) / 2 : 25.7;
  return grid ? (grid.cols * Math.cos((midLat * Math.PI) / 180)) / grid.rows : 2.07;
}

export function roughly(km2) {
  if (km2 < 1000) return `${Math.round(km2 / 10) * 10}`;
  return `${Math.round(km2 / 1000).toLocaleString("en")},000`;
}
