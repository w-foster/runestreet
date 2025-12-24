import React, { useMemo, useState } from "react";
import { Sparkline } from "../components/Sparkline";

type VolumeMode = "absolute" | "relative_to_baseline" | "daily_pct";

type ScanRequest = {
  baseline_hours: number;
  event_window_blocks: number;
  still_low_blocks: number;
  min_drop_pct: number;
  volume_mode: VolumeMode;
  min_event_volume: number;
  volume_multiplier: number;
  min_event_daily_pct: number;
  still_low_pct: number;
  min_buy_limit?: number;
  max_buy_limit?: number;
  min_price?: number;
  max_price?: number;
  min_daily_volume_24h?: number;
  max_daily_volume_24h?: number;
  sort_by: "biggest_drop" | "most_recent" | "biggest_volume" | "biggest_event_daily_pct";
  limit: number;
};

type ScanResult = {
  item_id: number;
  name: string;
  dump_bucket_ts: number;
  baseline_price: number;
  event_price: number;
  price_drop_pct: number;
  event_volume: number;
  still_low: boolean;
  daily_volume_24h?: number | null;
  event_daily_pct?: number | null;
};

type ScanResponse = {
  results: ScanResult[];
  meta: Record<string, unknown>;
};

type SpreadsRequest = {
  min_daily_volume_24h?: number;
  max_daily_volume_24h?: number;
  min_avg_price?: number;
  max_avg_price?: number;
  min_buy_limit?: number;
  sort_by: "score" | "spread_pct" | "spread_abs" | "stability_1y";
  stability_top_k: number;
  limit: number;
};

type SpreadsResult = {
  item_id: number;
  name: string;
  buy_limit?: number | null;
  daily_volume_24h: number;
  daily_mid_price?: number | null;
  spread_abs_median?: number | null;
  spread_pct_median?: number | null;
  stability_cv_1d?: number | null;
  stability_cv_7d?: number | null;
  stability_cv_30d?: number | null;
  stability_cv_1y?: number | null;
  score: number;
};

type SpreadsResponse = {
  results: SpreadsResult[];
  meta: Record<string, unknown>;
};

function apiBaseUrl(): string {
  const v = import.meta.env.VITE_API_BASE_URL as string | undefined;
  return v ?? "http://localhost:8000";
}

export function App() {
  const [tab, setTab] = useState<"dump" | "spreads">("dump");
  const base = apiBaseUrl();

  return (
    <div style={{ fontFamily: "system-ui, sans-serif", padding: 20, maxWidth: 1100, margin: "0 auto" }}>
      <h1 style={{ margin: 0 }}>Runestreet</h1>
      <p style={{ marginTop: 8, color: "#555" }}>OSRS scanning tools (on-demand, cached in Postgres).</p>

      <div style={{ display: "flex", gap: 8, margin: "12px 0 18px" }}>
        <button
          onClick={() => setTab("dump")}
          style={{
            padding: "8px 12px",
            border: "1px solid #ddd",
            background: tab === "dump" ? "#f5f3ff" : "white",
          }}
        >
          Dump detector
        </button>
        <button
          onClick={() => setTab("spreads")}
          style={{
            padding: "8px 12px",
            border: "1px solid #ddd",
            background: tab === "spreads" ? "#f5f3ff" : "white",
          }}
        >
          Spreads detector
        </button>
      </div>

      {tab === "dump" ? <DumpTab apiBase={base} /> : <SpreadsTab apiBase={base} />}
    </div>
  );
}

function DumpTab({ apiBase }: { apiBase: string }) {
  const [req, setReq] = useState<ScanRequest>({
    baseline_hours: 6,
    event_window_blocks: 1,
    still_low_blocks: 3,
    min_drop_pct: 0.07,
    volume_mode: "relative_to_baseline",
    min_event_volume: 0,
    volume_multiplier: 3,
    min_event_daily_pct: 0.1,
    still_low_pct: 0.05,
    sort_by: "biggest_drop",
    limit: 50,
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<ScanResponse | null>(null);

  const endpoint = useMemo(() => `${apiBase}/api/scan`, [apiBase]);

  async function runScan() {
    setLoading(true);
    setError(null);
    try {
      const resp = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(req),
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      setData((await resp.json()) as ScanResponse);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <h2 style={{ margin: "0 0 8px" }}>Dump detector</h2>
      <p style={{ marginTop: 0, color: "#555" }}>
        Configure filters, click Run, and the backend will ingest missing 5m buckets + scan cached data.
      </p>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: 12 }}>
        <label>
          Baseline hours
          <input
            type="number"
            value={req.baseline_hours}
            min={1}
            max={30}
            onChange={(e) => setReq({ ...req, baseline_hours: Number(e.target.value) })}
            style={{ width: "100%" }}
          />
        </label>
        <label>
          Event window blocks (5m)
          <input
            type="number"
            value={req.event_window_blocks}
            min={1}
            max={12}
            onChange={(e) => setReq({ ...req, event_window_blocks: Number(e.target.value) })}
            style={{ width: "100%" }}
          />
        </label>
        <label>
          Still-low blocks (5m)
          <input
            type="number"
            value={req.still_low_blocks}
            min={0}
            max={36}
            onChange={(e) => setReq({ ...req, still_low_blocks: Number(e.target.value) })}
            style={{ width: "100%" }}
          />
        </label>

        <label>
          Min drop pct (e.g. 0.07 = 7%)
          <input
            type="number"
            step="0.01"
            value={req.min_drop_pct}
            min={0}
            max={0.95}
            onChange={(e) => setReq({ ...req, min_drop_pct: Number(e.target.value) })}
            style={{ width: "100%" }}
          />
        </label>
        <label>
          Still-low pct vs baseline
          <input
            type="number"
            step="0.01"
            value={req.still_low_pct}
            min={0}
            max={0.95}
            onChange={(e) => setReq({ ...req, still_low_pct: Number(e.target.value) })}
            style={{ width: "100%" }}
          />
        </label>
        <label>
          Result limit
          <input
            type="number"
            value={req.limit}
            min={1}
            max={500}
            onChange={(e) => setReq({ ...req, limit: Number(e.target.value) })}
            style={{ width: "100%" }}
          />
        </label>

        <label>
          Sort by
          <select
            value={req.sort_by}
            onChange={(e) => setReq({ ...req, sort_by: e.target.value as ScanRequest["sort_by"] })}
            style={{ width: "100%" }}
          >
            <option value="biggest_drop">Biggest dip</option>
            <option value="biggest_event_daily_pct">Biggest event as % of daily vol</option>
            <option value="biggest_volume">Biggest event volume</option>
            <option value="most_recent">Most recent dump</option>
          </select>
        </label>

        <label>
          Min buy limit (optional)
          <input
            type="number"
            value={req.min_buy_limit ?? ""}
            min={0}
            onChange={(e) =>
              setReq({ ...req, min_buy_limit: e.target.value === "" ? undefined : Number(e.target.value) })
            }
            style={{ width: "100%" }}
          />
        </label>

        <label>
          Max buy limit (optional)
          <input
            type="number"
            value={req.max_buy_limit ?? ""}
            min={0}
            onChange={(e) =>
              setReq({ ...req, max_buy_limit: e.target.value === "" ? undefined : Number(e.target.value) })
            }
            style={{ width: "100%" }}
          />
        </label>

        <label>
          Min baseline price (optional)
          <input
            type="number"
            value={req.min_price ?? ""}
            min={0}
            onChange={(e) => setReq({ ...req, min_price: e.target.value === "" ? undefined : Number(e.target.value) })}
            style={{ width: "100%" }}
          />
        </label>

        <label>
          Max baseline price (optional)
          <input
            type="number"
            value={req.max_price ?? ""}
            min={0}
            onChange={(e) => setReq({ ...req, max_price: e.target.value === "" ? undefined : Number(e.target.value) })}
            style={{ width: "100%" }}
          />
        </label>

        <label>
          Volume mode
          <select
            value={req.volume_mode}
            onChange={(e) => setReq({ ...req, volume_mode: e.target.value as VolumeMode })}
            style={{ width: "100%" }}
          >
            <option value="relative_to_baseline">Relative to baseline</option>
            <option value="absolute">Absolute</option>
            <option value="daily_pct">Event as % of daily volume</option>
          </select>
        </label>

        {req.volume_mode === "absolute" ? (
          <label>
            Min event volume
            <input
              type="number"
              value={req.min_event_volume}
              min={0}
              onChange={(e) => setReq({ ...req, min_event_volume: Number(e.target.value) })}
              style={{ width: "100%" }}
            />
          </label>
        ) : req.volume_mode === "daily_pct" ? (
          <label>
            Min event daily pct (0.10 = 10%)
            <input
              type="number"
              step="0.01"
              value={req.min_event_daily_pct}
              min={0}
              max={1}
              onChange={(e) => setReq({ ...req, min_event_daily_pct: Number(e.target.value) })}
              style={{ width: "100%" }}
            />
          </label>
        ) : (
          <label>
            Volume multiplier
            <input
              type="number"
              step="0.1"
              value={req.volume_multiplier}
              min={0}
              onChange={(e) => setReq({ ...req, volume_multiplier: Number(e.target.value) })}
              style={{ width: "100%" }}
            />
          </label>
        )}

        <label>
          Min daily volume (24h, optional)
          <input
            type="number"
            value={req.min_daily_volume_24h ?? ""}
            min={0}
            onChange={(e) =>
              setReq({ ...req, min_daily_volume_24h: e.target.value === "" ? undefined : Number(e.target.value) })
            }
            style={{ width: "100%" }}
          />
        </label>

        <label>
          Max daily volume (24h, optional)
          <input
            type="number"
            value={req.max_daily_volume_24h ?? ""}
            min={0}
            onChange={(e) =>
              setReq({ ...req, max_daily_volume_24h: e.target.value === "" ? undefined : Number(e.target.value) })
            }
            style={{ width: "100%" }}
          />
        </label>
      </div>

      <div style={{ display: "flex", gap: 12, alignItems: "center", marginTop: 16 }}>
        <button onClick={runScan} disabled={loading} style={{ padding: "8px 14px" }}>
          {loading ? "Running..." : "Run"}
        </button>
        <code style={{ color: "#666" }}>{endpoint}</code>
      </div>

      {error ? <p style={{ color: "crimson" }}>{error}</p> : null}

      <div style={{ marginTop: 16 }}>
        <h3 style={{ marginBottom: 8 }}>Results</h3>
        {!data ? (
          <p style={{ color: "#666" }}>No results yet.</p>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                <th style={{ textAlign: "left", borderBottom: "1px solid #ddd", padding: 8 }}>Item</th>
                <th style={{ textAlign: "right", borderBottom: "1px solid #ddd", padding: 8 }}>Drop %</th>
                <th style={{ textAlign: "right", borderBottom: "1px solid #ddd", padding: 8 }}>Event vol</th>
                <th style={{ textAlign: "right", borderBottom: "1px solid #ddd", padding: 8 }}>Event % daily</th>
                <th style={{ textAlign: "right", borderBottom: "1px solid #ddd", padding: 8 }}>Daily vol (24h)</th>
                <th style={{ textAlign: "right", borderBottom: "1px solid #ddd", padding: 8 }}>Baseline</th>
                <th style={{ textAlign: "right", borderBottom: "1px solid #ddd", padding: 8 }}>Event</th>
                <th style={{ textAlign: "left", borderBottom: "1px solid #ddd", padding: 8 }}>Still low</th>
              </tr>
            </thead>
            <tbody>
              {data.results.flatMap((r) => [
                <tr key={`${r.item_id}:${r.dump_bucket_ts}:main`}>
                  <td style={{ padding: 8, borderBottom: "1px solid #f0f0f0" }}>
                    {r.name} <span style={{ color: "#888" }}>({r.item_id})</span>
                  </td>
                  <td style={{ padding: 8, borderBottom: "1px solid #f0f0f0", textAlign: "right" }}>
                    {(r.price_drop_pct * 100).toFixed(2)}%
                  </td>
                  <td style={{ padding: 8, borderBottom: "1px solid #f0f0f0", textAlign: "right" }}>{r.event_volume}</td>
                  <td style={{ padding: 8, borderBottom: "1px solid #f0f0f0", textAlign: "right" }}>
                    {r.event_daily_pct == null ? "-" : `${(r.event_daily_pct * 100).toFixed(2)}%`}
                  </td>
                  <td style={{ padding: 8, borderBottom: "1px solid #f0f0f0", textAlign: "right" }}>
                    {r.daily_volume_24h == null ? "-" : r.daily_volume_24h}
                  </td>
                  <td style={{ padding: 8, borderBottom: "1px solid #f0f0f0", textAlign: "right" }}>
                    {r.baseline_price.toFixed(1)}
                  </td>
                  <td style={{ padding: 8, borderBottom: "1px solid #f0f0f0", textAlign: "right" }}>{r.event_price.toFixed(1)}</td>
                  <td style={{ padding: 8, borderBottom: "1px solid #f0f0f0" }}>{r.still_low ? "yes" : "no"}</td>
                </tr>,
                <tr key={`${r.item_id}:${r.dump_bucket_ts}:chart`}>
                  <td colSpan={8} style={{ padding: "8px 8px 14px", borderBottom: "1px solid #f7f7f7" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                      <div style={{ color: "#666", fontSize: 12, width: 120 }}>last 24h price</div>
                      <Sparkline apiBaseUrl={apiBase} itemId={r.item_id} hours={24} />
                    </div>
                  </td>
                </tr>,
              ])}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

function SpreadsTab({ apiBase }: { apiBase: string }) {
  const [req, setReq] = useState<SpreadsRequest>({
    sort_by: "score",
    stability_top_k: 150,
    limit: 50,
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<SpreadsResponse | null>(null);

  const endpoint = useMemo(() => `${apiBase}/api/spreads/scan`, [apiBase]);

  async function run() {
    setLoading(true);
    setError(null);
    try {
      const resp = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(req),
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      setData((await resp.json()) as SpreadsResponse);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ border: "1px solid #eee", padding: 14, borderRadius: 8 }}>
      <h2 style={{ margin: "0 0 8px" }}>Spreads detector</h2>
      <p style={{ marginTop: 0, color: "#555" }}>
        Finds items with a consistently realisable spread today, then rewards stability over 7/30/365 days (daily points).
      </p>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: 12 }}>
        <label>
          Min daily vol (24h)
          <input
            type="number"
            value={req.min_daily_volume_24h ?? ""}
            min={0}
            onChange={(e) =>
              setReq({ ...req, min_daily_volume_24h: e.target.value === "" ? undefined : Number(e.target.value) })
            }
            style={{ width: "100%" }}
          />
        </label>
        <label>
          Max daily vol (24h)
          <input
            type="number"
            value={req.max_daily_volume_24h ?? ""}
            min={0}
            onChange={(e) =>
              setReq({ ...req, max_daily_volume_24h: e.target.value === "" ? undefined : Number(e.target.value) })
            }
            style={{ width: "100%" }}
          />
        </label>
        <label>
          Min buy limit
          <input
            type="number"
            value={req.min_buy_limit ?? ""}
            min={0}
            onChange={(e) =>
              setReq({ ...req, min_buy_limit: e.target.value === "" ? undefined : Number(e.target.value) })
            }
            style={{ width: "100%" }}
          />
        </label>

        <label>
          Min avg price
          <input
            type="number"
            value={req.min_avg_price ?? ""}
            min={0}
            onChange={(e) => setReq({ ...req, min_avg_price: e.target.value === "" ? undefined : Number(e.target.value) })}
            style={{ width: "100%" }}
          />
        </label>
        <label>
          Max avg price
          <input
            type="number"
            value={req.max_avg_price ?? ""}
            min={0}
            onChange={(e) => setReq({ ...req, max_avg_price: e.target.value === "" ? undefined : Number(e.target.value) })}
            style={{ width: "100%" }}
          />
        </label>

        <label>
          Sort by
          <select
            value={req.sort_by}
            onChange={(e) => setReq({ ...req, sort_by: e.target.value as SpreadsRequest["sort_by"] })}
            style={{ width: "100%" }}
          >
            <option value="score">Score (spread + stability)</option>
            <option value="spread_pct">Spread % (median)</option>
            <option value="spread_abs">Spread gp (median)</option>
            <option value="stability_1y">Most stable (1y)</option>
          </select>
        </label>

        <label>
          Stability shortlist size
          <input
            type="number"
            value={req.stability_top_k}
            min={10}
            max={500}
            onChange={(e) => setReq({ ...req, stability_top_k: Number(e.target.value) })}
            style={{ width: "100%" }}
          />
        </label>

        <label>
          Result limit
          <input
            type="number"
            value={req.limit}
            min={1}
            max={200}
            onChange={(e) => setReq({ ...req, limit: Number(e.target.value) })}
            style={{ width: "100%" }}
          />
        </label>
      </div>

      <div style={{ display: "flex", gap: 12, alignItems: "center", marginTop: 12 }}>
        <button onClick={run} disabled={loading} style={{ padding: "8px 14px" }}>
          {loading ? "Running..." : "Run"}
        </button>
        <code style={{ color: "#666" }}>{endpoint}</code>
      </div>

      {error ? <p style={{ color: "crimson" }}>{error}</p> : null}

      <div style={{ marginTop: 12 }}>
        {!data ? (
          <p style={{ color: "#666" }}>No results yet.</p>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                <th style={{ textAlign: "left", borderBottom: "1px solid #ddd", padding: 8 }}>Item</th>
                <th style={{ textAlign: "right", borderBottom: "1px solid #ddd", padding: 8 }}>Score</th>
                <th style={{ textAlign: "right", borderBottom: "1px solid #ddd", padding: 8 }}>Spread %</th>
                <th style={{ textAlign: "right", borderBottom: "1px solid #ddd", padding: 8 }}>Spread gp</th>
                <th style={{ textAlign: "right", borderBottom: "1px solid #ddd", padding: 8 }}>Daily vol</th>
                <th style={{ textAlign: "right", borderBottom: "1px solid #ddd", padding: 8 }}>Avg price</th>
                <th style={{ textAlign: "right", borderBottom: "1px solid #ddd", padding: 8 }}>CV 1d</th>
                <th style={{ textAlign: "right", borderBottom: "1px solid #ddd", padding: 8 }}>CV 7d</th>
                <th style={{ textAlign: "right", borderBottom: "1px solid #ddd", padding: 8 }}>CV 30d</th>
                <th style={{ textAlign: "right", borderBottom: "1px solid #ddd", padding: 8 }}>CV 1y</th>
              </tr>
            </thead>
            <tbody>
              {data.results.map((r) => (
                <tr key={r.item_id}>
                  <td style={{ padding: 8, borderBottom: "1px solid #f0f0f0" }}>
                    {r.name} <span style={{ color: "#888" }}>({r.item_id})</span>
                  </td>
                  <td style={{ padding: 8, borderBottom: "1px solid #f0f0f0", textAlign: "right" }}>{r.score.toFixed(2)}</td>
                  <td style={{ padding: 8, borderBottom: "1px solid #f0f0f0", textAlign: "right" }}>
                    {r.spread_pct_median == null ? "-" : `${(r.spread_pct_median * 100).toFixed(2)}%`}
                  </td>
                  <td style={{ padding: 8, borderBottom: "1px solid #f0f0f0", textAlign: "right" }}>
                    {r.spread_abs_median == null ? "-" : r.spread_abs_median.toFixed(0)}
                  </td>
                  <td style={{ padding: 8, borderBottom: "1px solid #f0f0f0", textAlign: "right" }}>{r.daily_volume_24h}</td>
                  <td style={{ padding: 8, borderBottom: "1px solid #f0f0f0", textAlign: "right" }}>
                    {r.daily_mid_price == null ? "-" : r.daily_mid_price.toFixed(0)}
                  </td>
                  <td style={{ padding: 8, borderBottom: "1px solid #f0f0f0", textAlign: "right" }}>
                    {r.stability_cv_1d == null ? "-" : r.stability_cv_1d.toFixed(3)}
                  </td>
                  <td style={{ padding: 8, borderBottom: "1px solid #f0f0f0", textAlign: "right" }}>
                    {r.stability_cv_7d == null ? "-" : r.stability_cv_7d.toFixed(3)}
                  </td>
                  <td style={{ padding: 8, borderBottom: "1px solid #f0f0f0", textAlign: "right" }}>
                    {r.stability_cv_30d == null ? "-" : r.stability_cv_30d.toFixed(3)}
                  </td>
                  <td style={{ padding: 8, borderBottom: "1px solid #f0f0f0", textAlign: "right" }}>
                    {r.stability_cv_1y == null ? "-" : r.stability_cv_1y.toFixed(3)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}


