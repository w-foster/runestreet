import React, { useEffect, useMemo, useState } from "react";

type SeriesResponse = {
  item_id: number;
  timestep_seconds: number;
  start_ts: number;
  end_ts: number;
  timestamps: number[];
  avg_low: Array<number | null>;
  avg_high: Array<number | null>;
};

function minMax(values: Array<number | null>): { min: number; max: number } | null {
  const finite: number[] = [];
  for (const v of values) if (v != null && Number.isFinite(v)) finite.push(v);
  if (finite.length < 2) return null;
  return { min: Math.min(...finite), max: Math.max(...finite) };
}

function toPointsScaled(
  values: Array<number | null>,
  width: number,
  height: number,
  min: number,
  max: number,
): string | null {
  const span = Math.max(1, max - min);

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
  const points = useMemo(() => {
    if (!data) return { low: null as string | null, high: null as string | null };
    const mmLow = minMax(data.avg_low);
    const mmHigh = minMax(data.avg_high);
    const mins = [mmLow?.min, mmHigh?.min].filter((x): x is number => typeof x === "number");
    const maxs = [mmLow?.max, mmHigh?.max].filter((x): x is number => typeof x === "number");
    if (mins.length === 0 || maxs.length === 0) return { low: null, high: null };
    const min = Math.min(...mins);
    const max = Math.max(...maxs);
    return {
      low: toPointsScaled(data.avg_low, width, height, min, max),
      high: toPointsScaled(data.avg_high, width, height, min, max),
    };
  }, [data]);

  if (err) return <div style={{ color: "crimson", fontSize: 12 }}>chart error: {err}</div>;
  if (!data) return <div style={{ color: "#777", fontSize: 12 }}>loading chart…</div>;

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img" aria-label="24h price sparkline">
      <rect x="0" y="0" width={width} height={height} fill="transparent" stroke="#eee" />
      {points.low ? <polyline points={points.low} fill="none" stroke="#16a34a" strokeWidth="1.5" /> : null}
      {points.high ? <polyline points={points.high} fill="none" stroke="#c2410c" strokeWidth="1.5" /> : null}
    </svg>
  );
}


