import Reveal from "../animations/Reveal.jsx";
import { formatDay } from "../utils.js";

const KM2_PER_SQUARE = 19; // a 1/24-degree square is about 4.6 km by 4.2 km at these latitudes

function intakeFlagsOn(status, day) {
  return status.recent_flags.filter((f) => f.source === "intake" && f.flagged_on === day);
}

// One sentence that settles "is there anything to worry about today?"
function todaySentence(status) {
  const day = formatDay(status.intake?.scene_date ?? status.gulf.scene_date);
  const intakeFlags = status.intake ? intakeFlagsOn(status, status.intake.scene_date).length : 0;
  const gulfCount = status.gulf?.hotspot_count ?? 0;
  if (intakeFlags === 0 && gulfCount === 0) return `Nothing stood out on ${day}.`;
  const parts = [];
  if (intakeFlags > 0) parts.push(`${intakeFlags} of the three intakes read far above their recent days`);
  if (gulfCount > 0) {
    parts.push(
      `unusual water covered about ${(gulfCount * KM2_PER_SQUARE).toLocaleString("en")} km² of the Gulf, ` +
        `the nearest part ${Math.round(status.gulf.nearest_km)} km from Doha`
    );
  }
  return `On ${day}, ${parts.join(", and ")}.`;
}

// What the last ten days looked like, in terms of where unusual water kept appearing.
function recentSentence(trajectory) {
  const checked = trajectory.daily.filter((d) => d.hotspot_count !== null).length;
  const withPatches = trajectory.daily.filter((d) => d.hotspot_count > 0).length;
  if (withPatches === 0) return `None of the last ${checked} days with images showed unusual water.`;

  const area = trajectory.recurring_area;
  const where = area
    ? `mostly in one place: ${area.km_from_shore <= 5 ? "along the shore" : `about ${area.km_from_shore} km offshore`}, ` +
      `about ${area.km_from_doha} km ${area.direction_from_doha} of Doha`
    : "in a different place each time";
  const movement =
    trajectory.trend.verdict === "approaching"
      ? `It has been moving toward Qatar, about ${Math.abs(trajectory.trend.slope_km_per_day).toFixed(0)} km a day.`
      : trajectory.trend.verdict === "receding"
        ? "It has been moving away from Qatar."
        : "It didn't move steadily toward any intake.";
  return `In the last ${checked} days with images, unusual water showed up on ${withPatches} of them, ${where}. ${movement}`;
}

export default function LatestCheck({ status, trajectory }) {
  if (!status) return null;

  return (
    <Reveal as="section" className="section" id="latest-check" aria-labelledby="latest-check-title">
      <h2 id="latest-check-title">Latest satellite check</h2>
      <div className="prose">
        <p>
          <strong>{todaySentence(status)}</strong>
          {trajectory && ` ${recentSentence(trajectory)}`}
        </p>
        <p>
          {status.flags_total === 0 ? "No flags have been raised." : `${status.flags_total} flags have been raised so far.`}{" "}
          A flag means one of two things: an intake reading far above its own recent days, or unusual water moving
          steadily toward Qatar. Checked on {formatDay(status.last_run_utc)}.
        </p>
      </div>

      {status.recent_flags.length > 0 && (
        <table className="flag-table">
          <caption>Flags, newest first</caption>
          <thead>
            <tr>
              <th scope="col">Date</th>
              <th scope="col">What was flagged</th>
              <th scope="col">Checked afterwards</th>
            </tr>
          </thead>
          <tbody>
            {status.recent_flags.map((f) => (
              <tr key={`${f.flagged_on}-${f.source}-${f.message}`}>
                <td>{formatDay(f.flagged_on)}</td>
                <td>{f.message}</td>
                <td>{f.review === "not reviewed" ? "Not yet" : f.review === "likely real" ? "Likely real" : "False alarm"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Reveal>
  );
}
