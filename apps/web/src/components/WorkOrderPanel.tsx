"use client";

import { useEffect, useState } from "react";
import CreateWOModal from "./CreateWOModal";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "/api/demo";

// MOCK: replace with field-ops auth session when user/role system is wired
const FIELD_TEAM_HANDLE = "FieldTeam_01";
// MOCK: replace with authenticated citizen session when wired
const CITIZEN_HANDLE = "Citizen_01";

interface WorkOrder {
  id: number;
  flood_node_id: number;
  flood_node_name: string;
  flood_node_district: string;
  status: string;
  action_type: string;
  assigned_unit: string;
  notes: string | null;
  approved_by: string | null;
  confirmed_by: string | null;
  water_level_m: number | null;
  dispatched_at: string | null;
  line_dispatched: boolean;
  line_dispatched_at: string | null;
}

const ACTION_LABELS: Record<string, string> = {
  pump_emergency: "ปั๊มฉุกเฉิน",
  pump_high:      "ปั๊ม (สูง)",
  pump_standard:  "ปั๊ม (ปกติ)",
  inspect:        "ตรวจสอบ",
};

const ACTION_OPTIONS = ["pump_emergency", "pump_high", "pump_standard", "inspect"] as const;

const STATUS_BADGE: Record<string, string> = {
  pending:    "bg-yellow-900 text-yellow-300",
  dispatched: "bg-green-900 text-green-300",
  done:       "bg-gray-700 text-gray-300",
  mismatch:   "bg-red-900 text-red-300",
};

interface MismatchNote {
  oldId: number;
  newId: number;
}

export default function WorkOrderPanel({ onCountChange }: { onCountChange?: (n: number) => void }) {
  const [orders, setOrders] = useState<WorkOrder[]>([]);
  const [confirming, setConfirming] = useState<number | null>(null);
  const [verifying, setVerifying] = useState<number | null>(null);
  const [mismatchNote, setMismatchNote] = useState<MismatchNote | null>(null);

  // Create WO modal
  const [showCreateModal, setShowCreateModal] = useState(false);

  // Inline edit state
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editAction, setEditAction] = useState("");
  const [editUnit, setEditUnit] = useState("");
  const [editNotes, setEditNotes] = useState("");
  const [saving, setSaving] = useState(false);

  // Resend LINE prompt
  const [resendPromptId, setResendPromptId] = useState<number | null>(null);
  const [resending, setResending] = useState(false);

  const fetchOrders = async () => {
    try {
      const res = await fetch(`${API_URL}/work-orders`);
      if (res.ok) {
        const data = (await res.json()) as WorkOrder[];
        setOrders(data);
        const pending = data.filter((w) => w.status === "pending").length;
        onCountChange?.(pending);
      }
    } catch {
      // ignore — API may not be ready
    }
  };

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void fetchOrders();
    const id = setInterval(() => void fetchOrders(), 10000);
    return () => clearInterval(id);
  }, []);

  // ── Confirm (field ops acknowledges execution) ───────────────────────────

  const handleConfirm = async (wo: WorkOrder) => {
    setConfirming(wo.id);
    try {
      const res = await fetch(`${API_URL}/work-orders/${wo.id}/confirm`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ confirmed_by: FIELD_TEAM_HANDLE }),
      });
      if (res.ok) await fetchOrders();
    } catch {
      // ignore
    } finally {
      setConfirming(null);
    }
  };

  // ── Verify ───────────────────────────────────────────────────────────────

  const handleVerify = async (wo: WorkOrder, outcome: "VERIFIED" | "MISMATCH") => {
    setVerifying(wo.id);
    setMismatchNote(null);
    try {
      const res = await fetch(`${API_URL}/work-orders/${wo.id}/verify`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ outcome, verified_by: CITIZEN_HANDLE }),
      });
      if (res.ok) {
        const data = (await res.json()) as { outcome: string; new_work_order_id?: number | null };
        if (data.outcome === "MISMATCH" && data.new_work_order_id) {
          setMismatchNote({ oldId: wo.id, newId: data.new_work_order_id });
        }
        await fetchOrders();
      }
    } catch {
      // ignore
    } finally {
      setVerifying(null);
    }
  };

  // ── Inline edit ──────────────────────────────────────────────────────────

  const startEdit = (wo: WorkOrder) => {
    setEditingId(wo.id);
    setEditAction(wo.action_type);
    setEditUnit(wo.assigned_unit);
    setEditNotes(wo.notes ?? "");
    setResendPromptId(null);
  };

  const cancelEdit = () => setEditingId(null);

  const handleSave = async (wo: WorkOrder) => {
    setSaving(true);
    try {
      const res = await fetch(`${API_URL}/work-orders/${wo.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action_type: editAction !== wo.action_type ? editAction : undefined,
          assigned_unit: editUnit !== wo.assigned_unit ? editUnit : undefined,
          notes: editNotes !== (wo.notes ?? "") ? editNotes || null : undefined,
        }),
      });
      if (res.ok) {
        const data = (await res.json()) as WorkOrder & { resend_required?: boolean };
        setEditingId(null);
        await fetchOrders();
        if (data.resend_required) setResendPromptId(wo.id);
      }
    } catch {
      // ignore
    } finally {
      setSaving(false);
    }
  };

  // ── Resend LINE ───────────────────────────────────────────────────────────

  const handleResendLine = async (woId: number) => {
    setResending(true);
    try {
      const res = await fetch(`${API_URL}/work-orders/${woId}/notify-line`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ line_options: {} }),
      });
      if (res.ok) {
        setResendPromptId(null);
        await fetchOrders();
      }
    } catch {
      // ignore
    } finally {
      setResending(false);
    }
  };

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <>
      {showCreateModal && (
        <CreateWOModal
          onClose={() => setShowCreateModal(false)}
          onCreated={() => void fetchOrders()}
        />
      )}

      <div className="space-y-2 p-4">
        {/* Header with create button */}
        <div className="flex items-center justify-between pb-1">
          <span className="text-[10px] font-medium uppercase tracking-wider text-gray-500">
            Work Orders
          </span>
          <button
            onClick={() => setShowCreateModal(true)}
            className="rounded bg-blue-700 px-2 py-0.5 text-[10px] font-medium text-white hover:bg-blue-600"
          >
            + สร้าง WO
          </button>
        </div>

        {mismatchNote && (
          <div className="rounded border border-amber-700 bg-amber-950 p-2 text-xs text-amber-300">
            ⚠ WO#{mismatchNote.oldId} MISMATCH — สร้าง WO#{mismatchNote.newId} ใหม่แล้ว รอฝ่ายปฏิบัติการ
          </div>
        )}

        {orders.length === 0 && (
          <p className="py-3 text-xs text-gray-500">ไม่มีคำสั่งงานในขณะนี้</p>
        )}

        {orders.map((wo) => (
          <div
            key={wo.id}
            className="rounded-lg border border-gray-700 bg-gray-800 p-3 text-xs"
          >
            {/* WO header row */}
            <div className="mb-1 flex items-start justify-between gap-2">
              <span className="font-medium text-white">
                WO#{wo.id} · {wo.flood_node_name}
              </span>
              <div className="flex shrink-0 items-center gap-1">
                {wo.line_dispatched && (
                  <span className="rounded bg-green-900 px-1 py-0.5 font-mono text-[9px] text-green-400">
                    LINE ✓
                  </span>
                )}
                <span
                  className={`rounded px-1.5 py-0.5 font-mono text-[10px] ${STATUS_BADGE[wo.status] ?? "bg-gray-700 text-gray-300"}`}
                >
                  {wo.status}
                </span>
              </div>
            </div>

            {/* Inline edit form */}
            {editingId === wo.id ? (
              <div className="mt-2 space-y-2">
                <div>
                  <label className="mb-0.5 block text-[10px] text-gray-400">ประเภทคำสั่ง</label>
                  <select
                    value={editAction}
                    onChange={(e) => setEditAction(e.target.value)}
                    className="w-full rounded border border-gray-600 bg-gray-700 px-2 py-1 text-xs text-white"
                  >
                    {ACTION_OPTIONS.map((a) => (
                      <option key={a} value={a}>{ACTION_LABELS[a] ?? a}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="mb-0.5 block text-[10px] text-gray-400">หน่วยงาน</label>
                  <input
                    type="text"
                    value={editUnit}
                    onChange={(e) => setEditUnit(e.target.value)}
                    className="w-full rounded border border-gray-600 bg-gray-700 px-2 py-1 text-xs text-white"
                  />
                </div>
                <div>
                  <label className="mb-0.5 block text-[10px] text-gray-400">บันทึก</label>
                  <textarea
                    value={editNotes}
                    onChange={(e) => setEditNotes(e.target.value)}
                    rows={2}
                    className="w-full rounded border border-gray-600 bg-gray-700 px-2 py-1 text-xs text-white"
                  />
                </div>
                <div className="flex gap-1.5">
                  <button
                    onClick={() => void handleSave(wo)}
                    disabled={saving}
                    className="flex-1 rounded bg-blue-600 px-2 py-1 text-xs font-medium text-white hover:bg-blue-500 disabled:opacity-50"
                  >
                    {saving ? "กำลังบันทึก…" : "บันทึก"}
                  </button>
                  <button
                    onClick={cancelEdit}
                    className="rounded px-2 py-1 text-xs text-gray-400 hover:text-gray-200"
                  >
                    ยกเลิก
                  </button>
                </div>
              </div>
            ) : (
              <>
                <p className="text-gray-400">
                  {ACTION_LABELS[wo.action_type] ?? wo.action_type}
                  {wo.water_level_m !== null && (
                    <span className="ml-1 text-gray-500">· {wo.water_level_m.toFixed(2)}m</span>
                  )}
                </p>
                <p className="mt-0.5 text-gray-500">
                  {wo.assigned_unit}
                  <span className="ml-1 font-mono text-[9px] text-orange-500">[SIMULATED]</span>
                </p>
                {wo.approved_by && (
                  <p className="mt-0.5 text-[10px] text-gray-600">
                    อนุมัติโดย: {wo.approved_by}
                  </p>
                )}
              </>
            )}

            {/* Resend LINE prompt (shown after edit when line was previously sent) */}
            {resendPromptId === wo.id && editingId !== wo.id && (
              <div className="mt-2 rounded border border-green-800 bg-green-950 p-2 text-[10px] text-green-300">
                WO นี้เคยส่ง LINE แล้ว ต้องการส่งข้อมูลที่แก้ไขอีกครั้งไหม?
                <div className="mt-1.5 flex gap-1.5">
                  <button
                    onClick={() => void handleResendLine(wo.id)}
                    disabled={resending}
                    className="rounded bg-green-700 px-2 py-0.5 text-[10px] font-medium text-white hover:bg-green-600 disabled:opacity-50"
                  >
                    {resending ? "กำลังส่ง…" : "ส่ง LINE อีกครั้ง"}
                  </button>
                  <button
                    onClick={() => setResendPromptId(null)}
                    className="rounded px-2 py-0.5 text-[10px] text-gray-400 hover:text-gray-200"
                  >
                    ข้าม
                  </button>
                </div>
              </div>
            )}

            {/* Pending: edit + field ops confirm buttons */}
            {wo.status === "pending" && editingId !== wo.id && (
              <div className="mt-2 flex gap-1.5">
                <button
                  onClick={() => void handleConfirm(wo)}
                  disabled={confirming === wo.id}
                  className="flex-1 rounded bg-blue-600 px-2 py-1 text-xs font-medium text-white transition hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {confirming === wo.id ? "กำลังส่ง…" : "ฝ่ายปฏิบัติการยืนยัน ▶"}
                </button>
                <button
                  onClick={() => startEdit(wo)}
                  className="rounded border border-gray-600 px-2 py-1 text-xs text-gray-400 hover:border-gray-400 hover:text-gray-200"
                  title="แก้ไขรายละเอียด"
                >
                  ✏
                </button>
              </div>
            )}

            {/* Dispatched: verify buttons */}
            {wo.status === "dispatched" && (
              <>
                <p className="mt-1.5 text-[10px] text-green-400">
                  ✓ dispatched · {wo.confirmed_by}
                  {wo.dispatched_at && (
                    <span className="ml-1 text-gray-500">
                      {new Date(wo.dispatched_at).toLocaleTimeString("th-TH")}
                    </span>
                  )}
                </p>
                <div className="mt-2 flex gap-1.5">
                  <button
                    onClick={() => void handleVerify(wo, "VERIFIED")}
                    disabled={verifying === wo.id}
                    className="flex-1 rounded bg-emerald-700 px-2 py-1 text-xs font-medium text-white transition hover:bg-emerald-600 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {verifying === wo.id ? "…" : "✅ น้ำลดแล้ว"}
                  </button>
                  <button
                    onClick={() => void handleVerify(wo, "MISMATCH")}
                    disabled={verifying === wo.id}
                    className="flex-1 rounded bg-amber-700 px-2 py-1 text-xs font-medium text-white transition hover:bg-amber-600 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {verifying === wo.id ? "…" : "⚠ ยังไม่ลด"}
                  </button>
                </div>
              </>
            )}

            {wo.status === "done" && (
              <p className="mt-1.5 text-[10px] text-gray-500">✓ ปิดแล้ว</p>
            )}

            {wo.status === "mismatch" && (
              <p className="mt-1.5 text-[10px] text-red-400">⚠ MISMATCH — escalated</p>
            )}
          </div>
        ))}
      </div>
    </>
  );
}
