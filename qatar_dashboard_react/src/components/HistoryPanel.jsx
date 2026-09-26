// "Has this happened before?" panel, ported from the static dashboard
// (qatar_dashboard/index.html, #historyPanel) with the same wording and source.
// The backtest result is deliberately NOT shown here yet: backtest_2008_red_tide.py
// hasn't been run against real data, and nothing gets displayed until it has.
export default function HistoryPanel() {
  return (
    <section className="panel" id="historyPanel">
      <div className="panel-head">
        <div>
          <div className="panel-title">Has this happened before?</div>
          <div className="panel-sub">
            The 2008–2009 Arabian Gulf red tide, the regional precedent for this dashboard
          </div>
        </div>
      </div>
      <div className="history-body">
        <p>
          In late August 2008, a bloom of the fish-killing dinoflagellate <em>Cochlodinium polykrikoides</em> was first
          observed near Dibba Al-Hassan, on the UAE's Gulf-of-Oman coast. It spread through the Strait of Hormuz into
          the Arabian Gulf, reaching <strong>Qatari and Iranian waters</strong>, and persisted for more than eight
          months, into at least May 2009. It remains the worst-documented red tide event in the region's modern
          record: massive fish kills, damaged coral reefs, and desalination plants in the UAE and Oman forced offline
          for weeks. Plant-level disruption specifically in Qatar isn't documented in the literature reviewed here,
          but the bloom itself reached Qatar's coastal waters.
        </p>
        <p className="history-source">
          Source: Richlen et al.,{" "}
          <a
            href="https://www.sciencedirect.com/science/article/abs/pii/S1568988309001048"
            target="_blank"
            rel="noopener noreferrer"
          >
            "The catastrophic 2008–2009 red tide in the Arabian gulf region"
          </a>
          , Harmful Algae (2010). A backtest of this dashboard's own detection method against archived 2008–2009
          satellite imagery, checking how much lead time it would actually have given, is in{" "}
          <span className="mono">backtest_2008_red_tide.py</span>; results get added here once that's been run against
          the real historical data.
        </p>
      </div>
    </section>
  );
}
