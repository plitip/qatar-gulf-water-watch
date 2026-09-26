export default function ThemeToggle({ theme, onToggle }) {
  // "auto" resolves against the OS preference so the label always matches
  // what's actually on screen, not just the raw stored setting.
  const systemDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  const isDark = theme === "dark" || (theme === "auto" && systemDark);

  return (
    <button className="theme-toggle" onClick={onToggle}>
      {isDark ? "Light mode" : "Dark mode"}
    </button>
  );
}
