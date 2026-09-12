"use client";

import { useEffect, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "/api/demo";
// MOCK: replace with coordinator auth session when user/role system is wired
const COORDINATOR_HANDLE = "Coordinator_01";

interface FloodNode {
  id: number;
  name: string;
  district: string;
  current_fused_level: number | null;
  n_reports: number;
}

interface DispatchPlan {
  action_type: string;
  assigned_unit: string;
  water_level_m: number | null;
  district: string;
  flood_node_name: string;
  n_reports: number;
}

interface LineOptions {
  include_node_name: boolean;
  include_water_level: boolean;
  include_action_type: boolean;
  include_assigned_unit: boolean;
  extra_notes: string;
}

const ACTION_OPTIONS = ["pump_emergency", "pump_high", "pump_standard", "inspect"] as const;
const ACTION_LABELS: Record<string, string> = {
  pump_emergency: "ปั๊มฉุกเฉิน",
  pump_high:      "ปั๊ม (สูง)",
  pump_standard:  "ปั๊ม (ปกติ)",
  inspect:        "ตรวจสอบ",
};

const LINE_FIELD_LABELS: { key: keyof LineOptions; label: string }[] = [
  { key: "include_node_name",     label: "ชื่อจุดน้ำท่วม" },
  { key: "include_water_level",   label: "ระดับน้ำ" },
  { key: "include_action_type",   label: "ประเภทคำสั่ง" },
  { key: "include_assigned_unit", label: "หน่วยงาน" },
];

interface Props {
  onClose: () => void;
  onCreated: () => void;
}

export default function CreateWOModal({ onClose, onCreated }: Props) {
  const [step, setStep] = useState<1 | 2>(1);

  // Step 1 state
  const [nodes, setNodes] = useState<FloodNode[]>([]);
  const [selectedNodeId, setSelectedNodeId] = useState<number | "">("");
  const [plan, setPlan] = useState<DispatchPlan | null>(null);
  const [planLoading, setPlanLoading] = useState(false);
  const [planError, setPlanError] = useState<string | null>(null);
  const [actionType, setActionType] = useState("");
  const [assignedUnit, setAssignedUnit] = useState("");
  const [notes, setNotes] = useState("");

  // Step 2 state
  const [notifyLine, setNotifyLine] = useState(false);
  const [lineOptions, setLineOptions] = useState<LineOptions>({
    include_node_name: true,
    include_water_level: true,
    include_action_type: true,
    include_assigned_unit: true,
    extra_notes: "",
  });
  const [linePreview, setLinePreview] = useState<string | null>(null);
  const [linePreviewLoading, setLinePreviewLoading] = useState(false);

  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  // Fetch flood nodes on mount
  useEffect(() => {
    fetch(`${API_URL}/flood-nodes`)
      .then((r) => (r.ok ? r.json() : []))
      .then((data) => setNodes(data as FloodNode[]))
      .catch(() => {});
  }, []);

  const fetchPlan = async (nodeId: number) => {
    setPlanLoading(true);
    setPlanError(null);
    setPlan(null);
    try {
      const r = await fetch(`${API_URL}/work-orders/plan-preview?flood_node_id=${nodeId}`);
      if (!r.ok) {
        const err = (await r.json()) as { detail?: string };
        setPlanError(err.detail ?? `ข้อผิดพลาด HTTP ${r.status}`);
        return;
      }
      const data = (await r.json()) as DispatchPlan;
      setPlan(data);
      setActionType(data.action_type);
      setAssignedUnit(data.assigned_unit);
    } catch {
      setPlanError("ไม่สามารถเชื่อมต่อ API ได้");
    } finally {
      setPlanLoading(false);
    }
  };

  const handleNodeChange = (nodeId: number) => {
    setSelectedNodeId(nodeId);
    void fetchPlan(nodeId);
  };

  // Live LINE preview — debounced, only when on step 2 and notifyLine is checked
  useEffect(() => {
    if (step !== 2 || !notifyLine || !plan) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLinePreviewLoading(true);
    const timer = setTimeout(async () => {
      try {
        const params = new URLSearchParams({
          flood_node_name: plan.flood_node_name,
          action_type: actionType,
          assigned_unit: assignedUnit,
          include_node_name: String(lineOptions.include_node_name),
          include_water_level: String(lineOptions.include_water_level),
          include_action_type: String(lineOptions.include_action_type),
          include_assigned_unit: String(lineOptions.include_assigned_unit),
        });
        if (lineOptions.extra_notes) params.set("extra_notes", lineOptions.extra_notes);
        if (plan.water_level_m !== null) params.set("water_level_m", String(plan.water_level_m));

        const r = await fetch(`${API_URL}/work-orders/line-preview?${params.toString()}`);
        if (r.ok) {
          const data = (await r.json()) as { message: string };
          setLinePreview(data.message);
        }
      } catch {
        // ignore preview errors
      } finally {
        setLinePreviewLoading(false);
      }
    }, 300);
    return () => { clearTimeout(timer); };
  }, [step, notifyLine, plan, actionType, assignedUnit, lineOptions]);

  const handleSubmit = async () => {
    if (selectedNodeId === "") return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      const r = await fetch(`${API_URL}/work-orders`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          flood_node_id: selectedNodeId,
          approved_by: COORDINATOR_HANDLE,
          action_type: actionType,
          assigned_unit: assignedUnit,
          notes: notes || null,
          notify_line: notifyLine,
          line_options: {
            include_node_name: lineOptions.include_node_name,
            include_water_level: lineOptions.include_water_level,
            include_action_type: lineOptions.include_action_type,
            include_assigned_unit: lineOptions.include_assigned_unit,
            extra_notes: lineOptions.extra_notes || null,
          },
        }),
      });
      if (!r.ok) {
        const err = (await r.json()) as { detail?: string };
        setSubmitError(err.detail ?? `ข้อผิดพลาด HTTP ${r.status}`);
        return;
      }
      onCreated();
      onClose();
    } catch {
      setSubmitError("ไม่สามารถเชื่อมต่อ API ได้");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70">
      <div className="w-full max-w-md rounded-xl border border-gray-700 bg-gray-900 p-6 shadow-2xl">
        {/* Header */}
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-white">
            สร้าง Work Order
            <span className="ml-2 font-mono text-[10px] text-gray-500">ขั้นตอน {step}/2</span>
          </h2>
          <button
            onClick={onClose}
            className="text-lg text-gray-500 hover:text-gray-300"
            aria-label="ปิด"
          >
            ✕
          </button>
        </div>

        {/* ── Step 1: Plan review ── */}
        {step === 1 && (
          <div className="space-y-4">
            {/* Node selector */}
            <div>
              <label className="mb-1 block text-xs text-gray-400">เลือกจุดน้ำท่วม</label>
              <select
                value={selectedNodeId}
                onChange={(e) => handleNodeChange(Number(e.target.value))}
                className="w-full rounded border border-gray-600 bg-gray-800 px-3 py-2 text-xs text-white"
              >
                <option value="">-- เลือกจุด --</option>
                {nodes.map((n) => (
                  <option key={n.id} value={n.id} disabled={(n.n_reports ?? 0) === 0}>
                    {n.name}
                    {(n.n_reports ?? 0) === 0 ? " · ไม่มีรายงาน (G7)" : ""}
                    {n.current_fused_level !== null
                      ? ` · ${n.current_fused_level.toFixed(2)}m`
                      : ""}
                  </option>
                ))}
              </select>
            </div>

            {planLoading && <p className="text-xs text-gray-400">กำลังโหลดแผน…</p>}
            {planError && (
              <p className="rounded bg-red-950 px-3 py-2 text-xs text-red-400">{planError}</p>
            )}

            {plan && !planLoading && (
              <>
                <div>
                  <label className="mb-1 block text-xs text-gray-400">ประเภทคำสั่ง</label>
                  <select
                    value={actionType}
                    onChange={(e) => setActionType(e.target.value)}
                    className="w-full rounded border border-gray-600 bg-gray-800 px-3 py-2 text-xs text-white"
                  >
                    {ACTION_OPTIONS.map((a) => (
                      <option key={a} value={a}>
                        {ACTION_LABELS[a] ?? a}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="mb-1 block text-xs text-gray-400">หน่วยงาน</label>
                  <input
                    type="text"
                    value={assignedUnit}
                    onChange={(e) => setAssignedUnit(e.target.value)}
                    className="w-full rounded border border-gray-600 bg-gray-800 px-3 py-2 text-xs text-white"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs text-gray-400">บันทึก (ไม่บังคับ)</label>
                  <textarea
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                    rows={2}
                    placeholder="ข้อมูลเพิ่มเติม…"
                    className="w-full rounded border border-gray-600 bg-gray-800 px-3 py-2 text-xs text-white placeholder-gray-600"
                  />
                </div>
                <p className="text-[10px] text-gray-500">
                  ระดับน้ำ: {plan.water_level_m?.toFixed(2) ?? "N/A"}m ·{" "}
                  {plan.district} · {plan.n_reports} รายงาน
                </p>
              </>
            )}

            <div className="flex justify-end gap-2 pt-1">
              <button
                onClick={onClose}
                className="rounded px-4 py-1.5 text-xs text-gray-400 hover:text-gray-200"
              >
                ยกเลิก
              </button>
              <button
                onClick={() => setStep(2)}
                disabled={!plan || planLoading}
                className="rounded bg-blue-600 px-4 py-1.5 text-xs font-medium text-white hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
              >
                ยืนยันแผน →
              </button>
            </div>
          </div>
        )}

        {/* ── Step 2: LINE OA options ── */}
        {step === 2 && (
          <div className="space-y-4">
            <label className="flex items-center gap-2 text-xs text-white">
              <input
                type="checkbox"
                checked={notifyLine}
                onChange={(e) => setNotifyLine(e.target.checked)}
                className="rounded"
              />
              ส่งแจ้งเตือน LINE OA
            </label>

            {notifyLine && (
              <div className="rounded border border-gray-700 bg-gray-800 p-3 space-y-2">
                <p className="text-[10px] font-medium text-gray-400">
                  เลือกข้อมูลที่จะส่ง{" "}
                  <span className="text-gray-600">(default: ทั้งหมด)</span>
                </p>
                {LINE_FIELD_LABELS.map(({ key, label }) => (
                  <label key={key} className="flex items-center gap-2 text-xs text-gray-300">
                    <input
                      type="checkbox"
                      checked={lineOptions[key] as boolean}
                      onChange={(e) =>
                        setLineOptions((prev) => ({ ...prev, [key]: e.target.checked }))
                      }
                    />
                    {label}
                  </label>
                ))}
                <div>
                  <label className="mb-1 block text-[10px] text-gray-400">
                    ข้อความเพิ่มเติม
                  </label>
                  <textarea
                    value={lineOptions.extra_notes}
                    onChange={(e) =>
                      setLineOptions((prev) => ({ ...prev, extra_notes: e.target.value }))
                    }
                    rows={2}
                    placeholder="หมายเหตุพิเศษ…"
                    className="w-full rounded border border-gray-600 bg-gray-700 px-2 py-1 text-xs text-white placeholder-gray-600"
                  />
                </div>

                {/* Live preview */}
                <div className="rounded border border-gray-600 bg-gray-900 p-2">
                  <p className="mb-1 text-[9px] text-gray-500">Preview ข้อความ LINE:</p>
                  {linePreviewLoading ? (
                    <p className="text-[10px] text-gray-500">กำลังโหลด…</p>
                  ) : linePreview ? (
                    <pre className="whitespace-pre-wrap font-mono text-[9px] text-green-300">
                      {linePreview}
                    </pre>
                  ) : (
                    <p className="text-[10px] text-gray-500">—</p>
                  )}
                </div>
              </div>
            )}

            {submitError && (
              <p className="rounded bg-red-950 px-3 py-2 text-xs text-red-400">{submitError}</p>
            )}

            <div className="flex justify-end gap-2 pt-1">
              <button
                onClick={() => setStep(1)}
                className="rounded px-4 py-1.5 text-xs text-gray-400 hover:text-gray-200"
              >
                ← ย้อนกลับ
              </button>
              <button
                onClick={() => void handleSubmit()}
                disabled={submitting}
                className="rounded bg-emerald-600 px-4 py-1.5 text-xs font-medium text-white hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {submitting ? "กำลังสร้าง…" : "สร้าง Work Order ✓"}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
