import { useRef } from "react";
import { gsap, useGSAP, prefersReducedMotion } from "./gsapSetup.js";

// Headline that rises in one letter at a time. Modelled on the "Split Text"
// component from React Bits (reactbits.dev), written here from scratch with
// plain GSAP so there's no extra dependency.
//
// Each word is wrapped in a no-wrap span so line breaks only happen between
// words, never in the middle of one. Screen readers get the plain text via
// aria-label; the per-letter spans are hidden from them.
export default function SplitText({ text, as: Tag = "h1", className = "", delay = 0 }) {
  const ref = useRef(null);

  useGSAP(
    () => {
      if (prefersReducedMotion()) return;
      gsap.from(ref.current.querySelectorAll(".split-char"), {
        yPercent: 110,
        opacity: 0,
        duration: 0.7,
        ease: "power3.out",
        stagger: 0.03,
        delay,
      });
    },
    { scope: ref }
  );

  const words = text.split(" ");

  return (
    <Tag ref={ref} className={className} aria-label={text}>
      {words.map((word, w) => (
        <span className="split-word" aria-hidden="true" key={w}>
          {[...word].map((ch, c) => (
            <span className="split-char" key={c}>
              {ch}
            </span>
          ))}
          {w < words.length - 1 ? " " : null}
        </span>
      ))}
    </Tag>
  );
}
