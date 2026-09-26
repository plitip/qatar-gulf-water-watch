// One place to register GSAP plugins so every component shares the same setup.
// GSAP (github.com/greensock/GSAP) is installed from npm as `gsap`; `@gsap/react`
// gives us the useGSAP() hook, which cleans animations up when a component
// unmounts (important under React StrictMode, which mounts effects twice in dev).
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { useGSAP } from "@gsap/react";

gsap.registerPlugin(ScrollTrigger, useGSAP);

// By default GSAP "smooths" lag: if frames arrive late it only advances ~33ms per
// frame, so on a slow or busy device a 1-second reveal can stretch to many
// seconds, with the content still invisible. Turning it off means every
// animation finishes on schedule, skipping frames if it has to. For a dashboard,
// getting the numbers on screen matters more than silky motion.
gsap.ticker.lagSmoothing(0);

// Anyone who has asked their OS for reduced motion gets the final state
// immediately, with no movement. Every animation checks this first.
export function prefersReducedMotion() {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

export { gsap, ScrollTrigger, useGSAP };
