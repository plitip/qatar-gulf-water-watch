import { useRef } from "react";
import { gsap, useGSAP, prefersReducedMotion } from "./gsapSetup.js";

// Number that counts up from 0 to `value` when it scrolls into view. Same idea
// as React Bits' "Count Up" component, done with a GSAP tween.
//
// The real value is rendered in the HTML from the start, so if JavaScript is
// slow, or motion is reduced, the reader still sees the correct number. The
// animation always ends on exactly the real value.
export default function CountUp({ value, decimals = 2, duration = 1.4, className = "" }) {
  const ref = useRef(null);

  useGSAP(
    () => {
      if (prefersReducedMotion()) return;
      const counter = { n: 0 };
      gsap.to(counter, {
        n: value,
        duration,
        ease: "power2.out",
        scrollTrigger: { trigger: ref.current, start: "top 90%", once: true },
        onUpdate: () => {
          ref.current.textContent = counter.n.toFixed(decimals);
        },
        onComplete: () => {
          ref.current.textContent = value.toFixed(decimals);
        },
      });
    },
    { dependencies: [value, decimals], scope: ref }
  );

  return (
    <span ref={ref} className={className}>
      {value.toFixed(decimals)}
    </span>
  );
}
