import { readFileSync } from "node:fs";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Security headers live in vercel.json (that's what production uses). `npm run
// preview` sends the same ones, so a Content-Security-Policy mistake shows up
// locally before it ever reaches the live site. Two are dropped for preview only,
// because it runs over plain http://localhost: HSTS and upgrade-insecure-requests.
function productionHeadersForLocalPreview() {
  const vercel = JSON.parse(readFileSync(new URL("./vercel.json", import.meta.url), "utf-8"));
  const siteWide = vercel.headers.find((rule) => rule.source === "/(.*)").headers;
  return Object.fromEntries(
    siteWide
      .filter(({ key }) => key !== "Strict-Transport-Security")
      .map(({ key, value }) => [
        key,
        key === "Content-Security-Policy" ? value.replace(/;\s*upgrade-insecure-requests/, "") : value,
      ])
  );
}

export default defineConfig({
  plugins: [react()],
  // Relative asset paths, so the built dist/ folder works whether it's served
  // from a domain root (Vercel) or a sub-path (GitHub Pages /repo-name/).
  base: "./",
  preview: {
    headers: productionHeadersForLocalPreview(),
  },
});
