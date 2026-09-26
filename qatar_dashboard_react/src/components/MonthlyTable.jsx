import { useState } from "react";
import { MONTH_NAMES } from "../utils.js";

// Every monthly value behind the charts, for anyone who'd rather read numbers than lines.
export default function MonthlyTable({ data, sites }) {
  const [open, setOpen] = useState(false);
  const months = data[sites[0]].map((d) => d.month);

  return (
    <div className="monthly-table">
      <button className="text-button" onClick={() => setOpen((v) => !v)} aria-expanded={open}>
        {open ? "Hide the monthly numbers" : "Show the monthly numbers"}
      </button>
      {open && (
        <div className="table-scroll">
          <table>
            <caption>Monthly average chlorophyll-a, mg/m³</caption>
            <thead>
              <tr>
                <th scope="col">Month</th>
                {sites.map((s) => (
                  <th scope="col" key={s}>
                    {s}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {[...months].reverse().map((m) => {
                const i = months.indexOf(m);
                return (
                  <tr key={m}>
                    <th scope="row">
                      {MONTH_NAMES[Number(m.slice(5)) - 1].slice(0, 3)} {m.slice(0, 4)}
                    </th>
                    {sites.map((s) => {
                      const v = data[s][i].v;
                      return <td key={s}>{v === null ? "No data" : v.toFixed(1)}</td>;
                    })}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
