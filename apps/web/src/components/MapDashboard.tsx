"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import WorkOrderPanel from "@/components/WorkOrderPanel";

const MapView = dynamic(() => import("@/components/MapView"), { ssr: false });

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "/api/demo";
const IS_DESIGN_DEMO = !process.env.NEXT_PUBLIC_API_URL;

const colors = {
  safe: "#2ea043",
  warn: "#d29922",
  danger: "#da3633",
  accent: "#388bfd",
  purple: "#a371f7",
  cyan: "#39c5cf",
  pink: "#f778ba",
  orange: "#ff9f1c",
  muted: "#8b949e",
  text: "#e6edf3",
};

interface Stats {
  flood_node_count: number;
  reports_today: number;
  work_orders_open: number;
}

export default function MapDashboard() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [activeTab, setActiveTab] = useState<"situation" | "bma">("situation");
  
  // Visibility layer set
  const [visibleLayers, setVisibleLayers] = useState<Set<string>>(
    new Set([
      "floodnode",
      "water-surface",
      "districts",
      "protection",
      "rivers",
      "canals",
      "tunnels",
      "pipejack",
      "sumps",
      "gates",
      "pumps",
      "waterlevel",
      "expo473",
      "roadflood"
    ])
  );

  const [activeCanalMode, setActiveCanalMode] = useState<string>("hierarchy");
  const [dangerViewEnabled, setDangerViewEnabled] = useState<boolean>(false);
  const [zoomVal, setZoomVal] = useState<number>(12);
  const [zoomLvlLabel, setZoomLvlLabel] = useState<string>("L2 Main");
  
  // BMA loaded stats
  const [bmaStats, setBmaStats] = useState<Record<string, any> | null>(null);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const res = await fetch(`${API_URL}/stats`);
        if (res.ok) setStats((await res.json()) as Stats);
      } catch {
        // ignore
      }
    };
    void fetchStats();
    const id = setInterval(() => void fetchStats(), 10000);
    return () => clearInterval(id);
  }, []);

  const statCards = [
    {
      label: "flood nodes (สถานี กทม.)",
      value: stats?.flood_node_count ?? null,
      note: stats
        ? IS_DESIGN_DEMO
          ? "SIMULATED-by-design"
          : "REAL (ข้อมูลจริง กทม.)"
        : "กำลังโหลด…",
    },
    {
      label: "รายงานวันนี้",
      value: stats?.reports_today ?? null,
      note: stats ? "SIMULATED-by-design" : "กำลังโหลด…",
    },
    {
      label: "work orders (pending)",
      value: stats?.work_orders_open ?? null,
      note: "รอยืนยันสั่งการ (G3 confirmation)",
    },
  ];

  const layerOrder = [
    { id: "floodnode", label: "สถานีตรวจวัดหลัก (Flood Nodes)", type: "dot", color: "#fbbf24", defCount: 0 },
    { id: "water-surface", label: "ระดับน้ำหลากจำลอง (Water Surface)", type: "sq", color: "#60a5fa", defCount: 625 },
    { id: "districts", label: "เขตการปกครอง (districts)", type: "bar", color: "#000000", defCount: 50 },
    { id: "protection", label: "พื้นที่ป้องกันน้ำท่วม", type: "sq", color: "#388bfd", defCount: 22 },
    { id: "rivers", label: "แม่น้ำสายหลัก (rivers)", type: "bar", color: "#60a5fa", defCount: 2 },
    { id: "canals", label: "คลอง (canals)", type: "bar", color: "#39c5cf", defCount: 2000 },
    { id: "tunnels", label: "อุโมงค์ (tunnels)", type: "bar", color: "#f778ba", defCount: 8 },
    { id: "pipejack", label: "ท่อดันลอด (pipe-jacking)", type: "bar", color: "#ff9f1c", defCount: 3 },
    { id: "pipes", label: "ท่อระบายน้ำ LIVE (ArcGIS)", type: "bar", color: "#6e7681", defCount: 81574 },
    { id: "sumps", label: "บ่อสูบน้ำ (sumps)", type: "dot", color: "#d2a8ff", defCount: 323 },
    { id: "gates", label: "ประตูระบายน้ำ (floodgates)", type: "dot", color: "#a371f7", defCount: 247 },
    { id: "pumps", label: "สถานีสูบน้ำ (pump stations)", type: "dot", color: "#ff9f1c", defCount: 191 },
    { id: "waterlevel", label: "สถานีวัดระดับ (water-level)", type: "dot", color: "#388bfd", defCount: 125 },
    { id: "expo473", label: "จุดเสี่ยง 473 (risk)", type: "dot", color: "#da3633", defCount: 473 },
    { id: "roadflood", label: "น้ำท่วมถนน (road-flood)", type: "dot", color: "#da3633", defCount: 32 },
  ];

  const toggleLayer = (id: string) => {
    setVisibleLayers((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const setAllLayers = (on: boolean) => {
    if (on) {
      setVisibleLayers(new Set(layerOrder.map((l) => l.id)));
    } else {
      setVisibleLayers(new Set());
    }
  };

  const handleZoomChange = (zoom: number, level: number) => {
    setZoomVal(zoom);
    const labels = {
      1: "L1 คลองหลัก",
      2: "L2 Main",
      3: "L3 น้ำ≥70%",
      4: "L4 ขนาดจริง",
    };
    setZoomLvlLabel((labels as any)[level] || "");
  };

  const getLayerCount = (id: string, def: number) => {
    if (id === "floodnode") return stats?.flood_node_count?.toLocaleString() || "—";
    if (id === "water-surface") return "625";
    if (!bmaStats) return def.toLocaleString();
    if (id === "districts") return bmaStats.districts.toLocaleString();
    if (id === "protection") return (bmaStats.protectionCount ?? 22).toLocaleString();
    if (id === "rivers") return (bmaStats.riversCount ?? 2).toLocaleString();
    if (id === "canals") return "2,000";
    if (id === "tunnels") return (bmaStats.tunnelsCount ?? 8).toLocaleString();
    if (id === "pipejack") return (bmaStats.pipejackCount ?? 3).toLocaleString();
    if (id === "pipes") return "81,574";
    if (id === "sumps") return bmaStats.sumpsCount.toLocaleString();
    if (id === "gates") return bmaStats.gatesCount.toLocaleString();
    if (id === "pumps") return bmaStats.pumpsCount.toLocaleString();
    if (id === "waterlevel") return bmaStats.waterLevelCount.toLocaleString();
    if (id === "expo473") return bmaStats.risk473Count.toLocaleString();
    if (id === "roadflood") return bmaStats.roadSensors.toLocaleString();
    return def.toLocaleString();
  };

  return (
    <div className="flex h-screen flex-col bg-gray-950 text-white font-sans">
      <header className="flex items-center justify-between border-b border-gray-800 px-4 py-3 bg-gray-900">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-md bg-blue-600 text-sm font-bold shadow-md">
            🌊
          </div>
          <div>
            <h1 className="text-sm font-semibold leading-none">Floodtir · Bangkok</h1>
            <p className="text-xs text-gray-400 mt-1">บูรณาการข้อมูล BMA SEDGIS + Thaiwater</p>
          </div>
        </div>
        <div className="flex items-center gap-2 text-xs text-gray-400">
          <a
            href="/design"
            target="_blank"
            rel="noopener noreferrer"
            className="rounded bg-cyan-950 px-2 py-0.5 font-mono text-cyan-300 hover:bg-cyan-900 hover:text-white transition-colors"
            title="Frontend-only system storyboard"
          >
            System Storyboard
          </a>
          <a
            href="/board"
            target="_blank"
            rel="noopener noreferrer"
            className="rounded bg-gray-800 px-2 py-0.5 font-mono hover:bg-gray-700 hover:text-white transition-colors"
            title="Accountability Board — ledger-backed events"
          >
            Accountability Board
          </a>
          <span className="text-gray-700">|</span>
          <span className="rounded bg-gray-800 px-2 py-0.5 font-mono text-gray-500">
            {IS_DESIGN_DEMO ? "status: design-demo" : "status: active-bma"}
          </span>
          <span className="text-gray-700">|</span>
          <span
            className={`rounded px-2 py-0.5 font-mono font-bold ${
              IS_DESIGN_DEMO
                ? "bg-orange-900/30 text-orange-400"
                : "bg-blue-900/30 text-blue-400"
            }`}
          >
            {IS_DESIGN_DEMO ? "Mock operations · no backend" : "PostGIS Live"}
          </span>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        {/* Main Map Content */}
        <main className="relative flex-1">
          <MapView
            visibleLayers={visibleLayers}
            activeCanalMode={activeCanalMode}
            dangerViewEnabled={dangerViewEnabled}
            onZoomChange={handleZoomChange}
            onStatsLoaded={setBmaStats}
          />

          {/* Map Overlays: Zoom & Legends */}
          <div className="absolute bottom-4 left-4 z-[1000] flex flex-col gap-2 pointer-events-none">
            {/* Zoom Badge */}
            <div className="rounded-lg border border-gray-850 bg-gray-900/90 px-3 py-1.5 text-[11px] font-mono text-gray-400 backdrop-blur shadow-lg pointer-events-auto">
              Zoom: <span className="text-white font-bold">{zoomVal}</span>
              <span className="text-cyan-400 ml-2 font-sans font-semibold">{zoomLvlLabel}</span>
            </div>

            {/* Road Flood Legend */}
            {visibleLayers.has("roadflood") && (
              <div className="rounded-lg border border-gray-800 bg-gray-900/90 p-3 text-xs backdrop-blur shadow-lg pointer-events-auto">
                <p className="mb-2 font-medium text-gray-300">ระดับน้ำท่วมถนน</p>
                <div className="space-y-1 text-gray-400">
                  {[
                    { color: colors.safe, label: "แห้งปกติ (0 ซม.)" },
                    { color: colors.warn, label: "น้ำขังตื้น (<10 ซม.)" },
                    { color: colors.danger, label: "น้ำท่วมขัง (≥10 ซม.)" },
                    { color: colors.muted, label: "ออฟไลน์" },
                  ].map(({ color, label }) => (
                    <div key={label} className="flex items-center gap-2">
                      <span
                        className="inline-block h-3 w-3 rounded-full border border-white"
                        style={{ backgroundColor: color }}
                      />
                      {label}
                    </div>
                  ))}
                </div>
              </div>
            )}
            
            {/* Live Pipes note */}
            {visibleLayers.has("pipes") && (
              <div
                id="pipenote"
                className="rounded-lg border border-yellow-700/50 bg-yellow-950/80 p-2.5 text-[11px] text-yellow-300 backdrop-blur shadow-lg pointer-events-auto max-w-xs"
              >
                Zoom in to level 15 to load pipes...
              </div>
            )}
          </div>
        </main>

        {/* Tabbed Aside panel */}
        <aside className="flex w-80 flex-col border-l border-gray-800 bg-gray-900 overflow-hidden">
          {/* Tabs header */}
          <div className="flex border-b border-gray-800 text-xs">
            <button
              onClick={() => setActiveTab("situation")}
              className={`flex-1 py-3 text-center font-medium border-b-2 transition-all ${
                activeTab === "situation"
                  ? "border-blue-500 text-white bg-gray-950/20 font-bold"
                  : "border-transparent text-gray-400 hover:text-white"
              }`}
            >
              💼 สถานการณ์ประสานงาน
            </button>
            <button
              onClick={() => setActiveTab("bma")}
              className={`flex-1 py-3 text-center font-medium border-b-2 transition-all ${
                activeTab === "bma"
                  ? "border-blue-500 text-white bg-gray-950/20 font-bold"
                  : "border-transparent text-gray-400 hover:text-white"
              }`}
            >
              🌊 ระบบข้อมูล BMA
            </button>
          </div>

          {/* Tab contents */}
          <div className="flex-1 overflow-y-auto custom-scrollbar">
            {activeTab === "situation" ? (
              <div className="flex flex-col h-full">
                {/* Stats cards */}
                <div className="border-b border-gray-800 p-4">
                  <h2 className="text-xs font-semibold uppercase tracking-wider text-gray-400 mb-3">สถานการณ์ภาพรวม</h2>
                  <div className="space-y-3">
                    {statCards.map(({ label, value, note }) => (
                      <div key={label} className="rounded-lg border border-gray-700 bg-gray-800 p-3">
                        <p className="text-xs text-gray-400">{label}</p>
                        <p className="mt-1 text-2xl font-bold tabular-nums">
                          {value !== null ? value : "—"}
                        </p>
                        <p className="text-xs text-gray-500 mt-1">{note}</p>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Work orders */}
                <div className="p-4 border-b border-gray-800">
                  <h2 className="text-xs font-semibold uppercase tracking-wider text-gray-400 mb-2">คำสั่งงานล่าสุด (Work Orders)</h2>
                  <WorkOrderPanel
                    onCountChange={(n) =>
                      setStats((prev) => (prev ? { ...prev, work_orders_open: n } : prev))
                    }
                  />
                </div>

                {/* Build Phase */}
                <div className="p-4 mt-auto">
                  <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-gray-400">Build Phases</p>
                  <div className="space-y-1 text-xs text-gray-400">
                    {[
                      { label: "P0 Scaffold", done: true },
                      { label: "P1 Ingest (BMA Telemetry)", done: true },
                      { label: "P2 Water surface (GIS Overlay)", done: true },
                      { label: "P3 Dispatch (G3 Human gate)", done: true },
                      { label: "P4 Citizen Verify & Ledger", done: true },
                    ].map(({ label, done }) => (
                      <div key={label} className="flex items-center gap-2">
                        <span>{done ? "✅" : "⬜"}</span>
                        <span className={done ? "text-white" : ""}>{label}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              <div className="p-4 space-y-4">
                {/* BMA Stats grid */}
                <div className="rounded-lg border border-gray-800 bg-gray-950/30 p-3">
                  <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-400 mb-2">สถิติข้อมูลแผนที่</h3>
                  <div className="grid grid-cols-2 gap-3 text-center">
                    <div className="rounded border border-gray-800 bg-gray-900 p-2">
                      <div className="text-lg font-bold text-blue-400">
                        {bmaStats ? bmaStats.totalFeatures.toLocaleString() : "กำลังโหลด"}
                      </div>
                      <div className="text-[10px] text-gray-500">ฟีเจอร์ทั้งหมด</div>
                    </div>
                    <div className="rounded border border-gray-800 bg-gray-900 p-2">
                      <div className="text-lg font-bold text-red-400">
                        {bmaStats ? bmaStats.floodedNow : 0}
                      </div>
                      <div className="text-[10px] text-gray-500">จุดท่วม ณ ขณะนี้</div>
                    </div>
                  </div>
                </div>

                {/* Layer selector */}
                <div className="rounded-lg border border-gray-800 bg-gray-950/30 p-3">
                  <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-400 mb-2">เลเยอร์แผนที่ (Layers)</h3>
                  
                  <div className="space-y-1.5 max-h-72 overflow-y-auto">
                    {layerOrder.map((layer) => {
                      const isChecked = visibleLayers.has(layer.id);
                      return (
                        <label key={layer.id} className="flex items-center gap-2 text-xs text-gray-300 hover:bg-gray-800 p-1 rounded cursor-pointer">
                          <input
                            type="checkbox"
                            checked={isChecked}
                            onChange={() => toggleLayer(layer.id)}
                            className="rounded border-gray-700 bg-gray-900 text-blue-600 focus:ring-blue-500 focus:ring-offset-gray-900"
                          />
                          <span
                            className="inline-block w-3 h-3 rounded-full border border-white/25 flex-none"
                            style={{ backgroundColor: layer.color }}
                          />
                          <span className={isChecked ? "text-white" : "text-gray-400"}>
                            {layer.label}
                          </span>
                          <span className="ml-auto text-[10px] text-gray-500 font-mono">
                            {getLayerCount(layer.id, layer.defCount)}
                          </span>
                        </label>
                      );
                    })}
                  </div>

                  <div className="flex gap-2 mt-3 border-t border-gray-800 pt-3">
                    <button
                      onClick={() => setAllLayers(true)}
                      className="flex-1 rounded bg-gray-800 py-1 text-[11px] font-medium hover:bg-gray-700 transition-colors"
                    >
                      แสดงทั้งหมด
                    </button>
                    <button
                      onClick={() => setAllLayers(false)}
                      className="flex-1 rounded bg-gray-800 py-1 text-[11px] font-medium hover:bg-gray-700 transition-colors"
                    >
                      ซ่อนทั้งหมด
                    </button>
                  </div>
                </div>

                {/* Canal settings */}
                {visibleLayers.has("canals") && (
                  <div className="rounded-lg border border-gray-800 bg-gray-950/30 p-3 space-y-3">
                    <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-400">แสดงสีคลอง (Canal Mode)</h3>
                    
                    <div className="space-y-2 text-xs">
                      {[
                        { id: "hierarchy", label: "ลำดับชั้น (Hierarchy)" },
                        { id: "status", label: "สถานะระดับน้ำ (Status)" },
                        { id: "capacity", label: "ระดับน้ำ/ความจุ (Capacity)" },
                      ].map((mode) => (
                        <label key={mode.id} className="flex items-center gap-2 cursor-pointer text-gray-300 hover:text-white">
                          <input
                            type="radio"
                            name="canal-mode"
                            checked={activeCanalMode === mode.id}
                            onChange={() => setActiveCanalMode(mode.id)}
                            className="border-gray-700 bg-gray-900 text-blue-600 focus:ring-blue-500 focus:ring-offset-gray-900"
                          />
                          <span>{mode.label}</span>
                        </label>
                      ))}
                    </div>

                    <div className="border-t border-gray-800 pt-2 text-[10px] text-gray-400 space-y-2">
                      <div>
                        <div className="font-semibold text-gray-200">ขนาดเส้น = ขนาดคลอง (Zoom ≥ 14)</div>
                        <div className="flex items-center gap-2 mt-1">
                          <span className="inline-block w-6 h-1 bg-cyan-400 rounded" />
                          <span>ใหญ่ (≥15 ม.)</span>
                        </div>
                        <div className="flex items-center gap-2 mt-0.5">
                          <span className="inline-block w-6 h-0.5 bg-cyan-800 rounded" />
                          <span>เล็ก (&lt;8 ม.)</span>
                        </div>
                      </div>

                      {activeCanalMode === "status" && (
                        <div>
                          <div className="font-semibold text-gray-200">สีเส้น = สถานะน้ำ</div>
                          <div className="flex items-center gap-2 mt-1">
                            <span className="inline-block w-3 h-1.5 bg-green-600 rounded" />
                            <span>ปกติ</span>
                          </div>
                          <div className="flex items-center gap-2 mt-0.5">
                            <span className="inline-block w-3 h-1.5 bg-yellow-600 rounded" />
                            <span>เฝ้าระวัง</span>
                          </div>
                          <div className="flex items-center gap-2 mt-0.5">
                            <span className="inline-block w-3 h-1.5 bg-red-600 rounded" />
                            <span>วิกฤต</span>
                          </div>
                        </div>
                      )}

                      {activeCanalMode === "capacity" && (
                        <div>
                          <div className="font-semibold text-gray-200">สีเส้น = % ความจุตลิ่ง</div>
                          <div className="flex items-center gap-2 mt-1">
                            <span className="inline-block w-3 h-1.5 bg-blue-500 rounded" />
                            <span>&lt;50% ปกติ</span>
                          </div>
                          <div className="flex items-center gap-2 mt-0.5">
                            <span className="inline-block w-3 h-1.5 bg-yellow-600 rounded" />
                            <span>50–80% เฝ้าระวัง</span>
                          </div>
                          <div className="flex items-center gap-2 mt-0.5">
                            <span className="inline-block w-3 h-1.5 bg-red-600 rounded" />
                            <span>&gt;80% ใกล้ล้นตลิ่ง</span>
                          </div>
                        </div>
                      )}
                    </div>

                    <button
                      onClick={() => setDangerViewEnabled((prev) => !prev)}
                      className={`w-full py-2 rounded text-xs font-semibold border transition-all text-left px-3 ${
                        dangerViewEnabled
                          ? "bg-red-950/40 border-red-500 text-red-400 font-bold"
                          : "bg-gray-800 border-gray-700 text-gray-400 hover:border-red-500 hover:text-red-400"
                      }`}
                    >
                      {dangerViewEnabled ? "⚠ ซ่อนสายน้ำอันตราย (Danger view)" : "⚠ แสดงสายน้ำอันตราย (Danger view)"}
                    </button>
                    <p className="text-[10px] text-gray-500 leading-tight">
                      วิเคราะห์คอขวดระบายน้ำ (Bottlenecks) และคลองเชื่อมต่อที่รับน้ำล้นจากจุดวิกฤตในเขตกรุงเทพฯ
                    </p>
                  </div>
                )}
              </div>
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}
