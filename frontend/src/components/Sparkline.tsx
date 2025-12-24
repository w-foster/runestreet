import React, { useEffect, useMemo, useState } from "react";

type SeriesResponse = {
  item_id: number;
  timestep_seconds: number;
  start_ts: number;
  end_ts: number;
  timestamps: number[];
  avg_low: Array<number | null>;
};

function toPoints(values: Array<number | null>, width: number, height: number): string | null {
  const finite: number[] = [];
  for (const v of values) if (v != null && Number.isFinite(v)) finite.push(v);
  if (finite.length < 2) return null;
  const min = Math.min(...finite);
  const max = Math.max(...finite);
  const span = Math.max(1, max - min);

  // Map indices to x; missing values are skipped (line breaks).
  const pts: string[] = [];
  const n = values.length;
  for (let i = 0; i < n; i++) {
    const v = values[i];
    if (v == null || !Number.isFinite(v)) continue;
    const x = (i / (n - 1)) * (width - 2) + 1;
    const y = height - 1 - ((v - min) / span) * (height - 2);
    pts.push(`${x.toFixed(2)},${y.toFixed(2)}`);
  }
  return pts.length >= 2 ? pts.join(" ") : null;
}

export function Sparkline({
  apiBaseUrl,
  itemId,
  hours = 24,
}: {
  apiBaseUrl: string;
  itemId: number;
  hours?: number;
}) {
  const [data, setData] = useState<SeriesResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    const ac = new AbortController();
    setErr(null);
    setData(null);

    fetch(`${apiBaseUrl}/api/items/${itemId}/series?hours=${hours}`, { signal: ac.signal })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((j) => setData(j as SeriesResponse))
      .catch((e) => {
        if (ac.signal.aborted) return;
        setErr(e instanceof Error ? e.message : String(e));
      });

    return () => ac.abort();
  }, [apiBaseUrl, itemId, hours]);

  const width = 280;
  const height = 44;
  const points = useMemo(() => (data ? toPoints(data.avg_low, width, height) : null), [data]);

  if (err) return <div style={{ color: "crimson", fontSize: 12 }}>chart error: {err}</div>;
  if (!data) return <div style={{ color: "#777", fontSize: 12 }}>loading chart…</div>;

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img" aria-label="24h price sparkline">
      <rect x="0" y="0" width={width} height={height} fill="transparent" stroke="#eee" />
      {points ? <polyline points={points} fill="none" stroke="#7c3aed" strokeWidth="1.5" /> : null}
    </svg>
  );
}


