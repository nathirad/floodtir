"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "/api/demo";

interface LedgerEntry {
  id: number;
  event_type: string;
  payload: string;
  prev_hash: string;
  hash: string;
  data_class: string;
  created_at: string;
}

// Re-compute SHA-256(event_type|payload|prev_hash) to verify chain integrity.
// Uses Web Crypto API — available in all modern browsers and Next.js server runtime.
async function sha256hex(str: string): Promise<string> {
  const buf = await crypto.subtle.digest(
    "SHA-256",
    new TextEncoder().encode(str),
  );
  return Array.from(new Uint8Array(buf))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

async function verifyChain(
  entries: LedgerEntry[],
): Promise<{ valid: boolean; brokenAt: number | null }> {
  const GENESIS = "0".repeat(64);
  for (const entry of entries) {
    const raw = `${entry.event_type}|${entry.payload}|${entry.prev_hash}`;
    const computed = await sha256hex(raw);
    if (computed !== entry.hash) {
      return { valid: false, brokenAt: entry.id };
    }
    // Check prev_hash links correctly to previous entry (skip genesis)
    const idx = entries.indexOf(entry);
    const expectedPrev = idx === 0 ? GENESIS : entries[idx - 1].hash;
    if (entry.prev_hash !== expectedPrev) {
      return { valid: false, brokenAt: entry.id };
    }
  }
  return { valid: true, brokenAt: null };
}

const EVENT_BADGE: Record<string, string> = {
  WO_CREATED: "bg-blue-900 text-blue-200",
  WO_DISPATCHED: "bg-green-900 text-green-200",
  VERIFY_OUTCOME: "bg-purple-900 text-purple-200",
  MISMATCH_ESCALATE: "bg-red-900 text-red-200",
};

const DATA_CLASS_BADGE: Record<string, string> = {
  "SIMULATED-by-design": "bg-orange-900 text-orange-300 border border-orange-700",
  REAL: "bg-emerald-900 text-emerald-300 border border-emerald-700",
  "PENDING-WIRE": "bg-gray-700 text-gray-400 border border-gray-600",
};

const EVENT_LABEL: Record<string, string> = {
  WO_CREATED: "สร้างคำสั่ง",
  WO_DISPATCHED: "ส่งหน่วย",
  VERIFY_OUTCOME: "ยืนยันผล",
  MISMATCH_ESCALATE: "Escalate",
};

function PayloadView({ raw }: { raw: string }) {
  let parsed: Record<string, unknown>;
  try {
    parsed = JSON.parse(raw) as Record<string, unknown>;
  } catch {
    return <span className="text-gray-400 text-xs font-mono">{raw}</span>;
  }
  return (
    <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-xs">
      {Object.entries(parsed).map(([k, v]) => (
        <div key={k} className="contents">
          <dt className="text-gray-500 font-mono">{k}</dt>
          <dd className="text-gray-300 font-mono truncate">
            {String(v ?? "—")}
          </dd>
        </div>
      ))}
    </dl>
  );
}

export default function AccountabilityBoard() {
  const [entries, setEntries] = useState<LedgerEntry[]>([]);
  const [chainOk, setChainOk] = useState<boolean | null>(null);
  const [brokenAt, setBrokenAt] = useState<number | null>(null);
  const [lastFetch, setLastFetch] = useState<Date | null>(null);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  async function fetchLedger() {
    try {
      const res = await fetch(`${API_URL}/ledger`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = (await res.json()) as LedgerEntry[];
      setEntries(data);
      setLastFetch(new Date());
      setError(null);

      const result = await verifyChain(data);
      setChainOk(result.valid);
      setBrokenAt(result.brokenAt);
    } catch (e) {
      setError(e instanceof Error ? e.message : "fetch error");
    }
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void fetchLedger();
    pollRef.current = setInterval(() => void fetchLedger(), 30_000);
    return () => {
      if (pollRef.current !== null) clearInterval(pollRef.current);
    };
  }, []);

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      {/* Header */}
      <header className="border-b border-gray-800 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link
            href="/"
            className="text-gray-400 hover:text-white text-sm transition-colors"
          >
            ← Map
          </Link>
          <h1 className="text-lg font-semibold">Accountability Board</h1>
          <span className="text-xs text-gray-500">
            Floodtir — Lat Krabang Pilot
          </span>
        </div>
        <div className="flex items-center gap-3 text-sm">
          {lastFetch && (
            <span className="text-gray-500 text-xs">
              อัปเดต {lastFetch.toLocaleTimeString("th-TH")}
            </span>
          )}
          <button
            onClick={() => void fetchLedger()}
            className="px-3 py-1 bg-gray-800 hover:bg-gray-700 rounded text-xs transition-colors"
          >
            รีเฟรช
          </button>
        </div>
      </header>

      {/* Chain status banner */}
      <div className="px-6 py-3 border-b border-gray-800">
        {chainOk === null ? (
          <div className="text-gray-500 text-sm">กำลังตรวจสอบ chain…</div>
        ) : chainOk ? (
          <div className="flex items-center gap-2 text-emerald-400 text-sm font-medium">
            <span>🔒</span>
            <span>
              Chain intact — {entries.length} events verified (SHA-256
              hash-chain)
            </span>
          </div>
        ) : (
          <div className="flex items-center gap-2 text-red-400 text-sm font-medium">
            <span>⚠</span>
            <span>Chain broken at entry #{brokenAt}</span>
          </div>
        )}
        {error && (
          <div className="text-red-400 text-xs mt-1">Error: {error}</div>
        )}
        <p className="text-gray-600 text-xs mt-1">
          G9: แสดงเฉพาะ ledger-backed facts — ไม่มี inference •
          Ed25519 signature: PENDING-WIRE
        </p>
      </div>

      {/* Entries */}
      <main className="px-6 py-4 max-w-4xl mx-auto">
        {entries.length === 0 && !error && (
          <div className="text-gray-600 text-sm py-12 text-center">
            ยังไม่มี ledger events — เริ่มต้น datagen หรือสร้าง work order
          </div>
        )}

        <div className="space-y-3">
          {entries.map((entry, idx) => (
            <div
              key={entry.id}
              className="bg-gray-900 border border-gray-800 rounded-lg p-4"
            >
              {/* Top row */}
              <div className="flex items-start justify-between gap-3 mb-3">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-gray-600 text-xs font-mono w-6 text-right">
                    #{entry.id}
                  </span>
                  <span
                    className={`px-2 py-0.5 rounded text-xs font-medium ${EVENT_BADGE[entry.event_type] ?? "bg-gray-700 text-gray-300"}`}
                  >
                    {EVENT_LABEL[entry.event_type] ?? entry.event_type}
                  </span>
                  <span className="text-gray-400 text-xs font-mono">
                    {entry.event_type}
                  </span>
                  <span
                    className={`px-2 py-0.5 rounded text-xs ${DATA_CLASS_BADGE[entry.data_class] ?? "bg-gray-700 text-gray-400"}`}
                  >
                    {entry.data_class}
                  </span>
                </div>
                <span className="text-gray-500 text-xs whitespace-nowrap">
                  {new Date(entry.created_at).toLocaleString("th-TH", {
                    day: "2-digit",
                    month: "2-digit",
                    hour: "2-digit",
                    minute: "2-digit",
                    second: "2-digit",
                  })}
                </span>
              </div>

              {/* Payload */}
              <div className="mb-3 pl-8">
                <PayloadView raw={entry.payload} />
              </div>

              {/* Hash chain row */}
              <div className="pl-8 border-t border-gray-800 pt-2 flex items-center gap-2 flex-wrap">
                <span className="text-gray-600 text-xs">
                  {idx === 0 ? "genesis" : `← #${entries[idx - 1].id}`}
                </span>
                <span className="text-gray-700 text-xs font-mono">
                  prev:{entry.prev_hash.slice(0, 8)}
                </span>
                <span className="text-gray-600 text-xs">→</span>
                <span className="text-gray-400 text-xs font-mono">
                  hash:{entry.hash.slice(0, 8)}
                </span>
              </div>
            </div>
          ))}
        </div>
      </main>
    </div>
  );
}
