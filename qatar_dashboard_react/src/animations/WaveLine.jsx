import { useRef } from "react";
import { gsap, useGSAP, prefersReducedMotion } from "./gsapSetup.js";

// Thin water-line under the headline: sweeps in from the left, then drifts
// slowly forever. Purely decorative, so it's hidden from screen readers.
//
// How the endless drift works: the path is one sine wave repeated across twice
// the visible width. Sliding it left by exactly one wavelength puts it back in a
// position that looks identical to the start, so repeat: -1 loops with no jump.
const WAVELENGTH = 60;
const AMPLITUDE = 4;
const VIEW_W = 600;
const VIEW_H = 14;

function buildWavePath() {
  const mid = VIEW_H / 2;
  let d = `M0,${mid}`;
  for (let x = 0; x < VIEW_W * 2 + WAVELENGTH; x += WAVELENGTH) {
    // two quadratic curves per wavelength: one crest, one trough
    d += ` Q${x + WAVELENGTH / 4},${mid - AMPLITUDE} ${x + WAVELENGTH / 2},${mid}`;
    d += ` Q${x + (3 * WAVELENGTH) / 4},${mid + AMPLITUDE} ${x + WAVELENGTH},${mid}`;
  }
  return d;
}

const WAVE_PATH = buildWavePath();

export default function WaveLine() {
  const ref = useRef(null);

  useGSAP(
    () => {
      if (prefersReducedMotion()) return;
      gsap.from(ref.current, {
        scaleX: 0,
        transformOrigin: "left center",
        duration: 1.2,
        ease: "power3.inOut",
        delay: 0.4,
      });
      gsap.to(ref.current.querySelector("path"), {
        x: -WAVELENGTH,
        duration: 2.6,
        ease: "none",
        repeat: -1,
      });
    },
    { scope: ref }
  );

  return (
    <svg
      ref={ref}
      className="wave-line"
      viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      <path d={WAVE_PATH} />
    </svg>
  );
}
