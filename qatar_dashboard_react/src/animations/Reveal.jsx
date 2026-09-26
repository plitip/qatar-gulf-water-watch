import { useRef } from "react";
import { gsap, useGSAP, prefersReducedMotion } from "./gsapSetup.js";

// Wrapper that fades and lifts its content into place as it scrolls into view
// (React Bits calls this "Animated Content"). With `stagger`, each direct child
// arrives one after another, which is how the three stat cards come in.
export default function Reveal({ children, as: Tag = "div", className = "", stagger = 0, y = 24, ...rest }) {
  const ref = useRef(null);

  useGSAP(
    () => {
      if (prefersReducedMotion()) return;
      const targets = stagger ? ref.current.children : ref.current;
      gsap.from(targets, {
        y,
        opacity: 0,
        duration: 0.8,
        ease: "power3.out",
        stagger,
        scrollTrigger: { trigger: ref.current, start: "top 88%", once: true },
      });
    },
    { scope: ref }
  );

  return (
    <Tag ref={ref} className={className} {...rest}>
      {children}
    </Tag>
  );
}
