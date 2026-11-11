export default function MapLegend() {
  return (
    <ul className="map-legend">
      <li>
        <span className="swatch" style={{ background: "var(--map-sea)" }} /> Normal for the month
      </li>
      <li>
        <span className="swatch" style={{ background: "var(--map-above)" }} /> Well above normal
      </li>
      <li>
        <span className="swatch" style={{ background: "var(--map-flagged)" }} /> Flagged by the check
      </li>
      <li>
        <span className="swatch" style={{ background: "var(--map-land)" }} /> Land
      </li>
    </ul>
  );
}
