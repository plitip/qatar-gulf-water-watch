import { formatDay } from "../utils.js";

// The freshest information, one line, near the top: the page is called "Watch", so it should
// say what the latest check found before telling the August story.
export default function StatusLine({ status }) {
  if (!status) return null;
  const sceneDate = status.intake?.scene_date ?? status.gulf?.scene_date;
  const flagsThatDay = status.recent_flags.filter((f) => f.flagged_on === sceneDate).length;
  return (
    <p className="status-line">
      Latest satellite images: {formatDay(sceneDate)}.{" "}
      <strong>{flagsThatDay === 0 ? "No flags." : `${flagsThatDay} flag${flagsThatDay > 1 ? "s" : ""}.`}</strong>{" "}
      <a href="#latest-check">What the check saw</a>
    </p>
  );
}
