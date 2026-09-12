/**
 * Frontend-only design API.
 *
 * This route intentionally mirrors the FastAPI contract with simulated data so
 * the product flow can be reviewed before the backend is wired. Supplying
 * NEXT_PUBLIC_API_URL makes the UI use the real API instead.
 */

type FloodNode = {
  id: number;
  name: string;
  district: string;
  lat: number;
  lon: number;
  current_fused_level: number | null;
  n_reports: number;
  last_updated: string;
};

type WorkOrder = {
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
  created_at: string;
  updated_at: string;
  dispatched_at: string | null;
  line_dispatched: boolean;
  line_dispatched_at: string | null;
  resend_required?: boolean;
};

const NOW = "2026-07-04T20:30:00.000Z";
const DISTRICT = "ลาดกระบัง";

const floodNodes: FloodNode[] = [
  { id: 1, name: "แยกร่มเกล้า–ลาดกระบัง", district: DISTRICT, lat: 13.7228, lon: 100.7478, current_fused_level: 0.84, n_reports: 6, last_updated: NOW },
  { id: 2, name: "ถนนเจ้าคุณทหาร", district: DISTRICT, lat: 13.7462, lon: 100.7805, current_fused_level: 0.58, n_reports: 4, last_updated: NOW },
  { id: 3, name: "ชุมชนหลวงแพ่ง", district: DISTRICT, lat: 13.7145, lon: 100.8334, current_fused_level: 1.12, n_reports: 8, last_updated: NOW },
  { id: 4, name: "คลองประเวศบุรีรมย์", district: DISTRICT, lat: 13.7287, lon: 100.8015, current_fused_level: 0.42, n_reports: 3, last_updated: NOW },
  { id: 5, name: "นิคมอุตสาหกรรมลาดกระบัง", district: DISTRICT, lat: 13.7604, lon: 100.7876, current_fused_level: 0.73, n_reports: 5, last_updated: NOW },
  { id: 6, name: "ตลาดหัวตะเข้", district: DISTRICT, lat: 13.7235, lon: 100.7833, current_fused_level: 0.31, n_reports: 2, last_updated: NOW },
  { id: 7, name: "ถนนฉลองกรุง ซอย 31", district: DISTRICT, lat: 13.7387, lon: 100.8179, current_fused_level: 0.66, n_reports: 4, last_updated: NOW },
  { id: 8, name: "สถานีสูบน้ำคลองสาม", district: DISTRICT, lat: 13.7509, lon: 100.8292, current_fused_level: 0.24, n_reports: 2, last_updated: NOW },
  { id: 9, name: "ถนนกิ่งแก้ว–ลาดกระบัง", district: DISTRICT, lat: 13.7088, lon: 100.7376, current_fused_level: 0.95, n_reports: 7, last_updated: NOW },
  { id: 10, name: "ชุมชนทับยาว", district: DISTRICT, lat: 13.7301, lon: 100.8468, current_fused_level: null, n_reports: 0, last_updated: NOW },
];

let workOrders: WorkOrder[] = [
  {
    id: 1042,
    flood_node_id: 3,
    flood_node_name: "ชุมชนหลวงแพ่ง",
    flood_node_district: DISTRICT,
    status: "pending",
    action_type: "pump_emergency",
    assigned_unit: "สำนักการระบายน้ำ · หน่วยเคลื่อนที่เร็ว 2",
    notes: "รอ Human confirmation (G3) ก่อนส่งหน่วย",
    approved_by: "Coordinator_01",
    confirmed_by: null,
    water_level_m: 1.12,
    created_at: "2026-07-04T20:21:00.000Z",
    updated_at: "2026-07-04T20:21:00.000Z",
    dispatched_at: null,
    line_dispatched: true,
    line_dispatched_at: "2026-07-04T20:22:00.000Z",
  },
  {
    id: 1041,
    flood_node_id: 1,
    flood_node_name: "แยกร่มเกล้า–ลาดกระบัง",
    flood_node_district: DISTRICT,
    status: "dispatched",
    action_type: "pump_high",
    assigned_unit: "สำนักงานเขตลาดกระบัง · ฝ่ายโยธา",
    notes: "ทีมภาคสนามรับงานแล้ว รอภาพยืนยันผล",
    approved_by: "Coordinator_01",
    confirmed_by: "FieldTeam_01",
    water_level_m: 0.84,
    created_at: "2026-07-04T19:56:00.000Z",
    updated_at: "2026-07-04T20:04:00.000Z",
    dispatched_at: "2026-07-04T20:04:00.000Z",
    line_dispatched: true,
    line_dispatched_at: "2026-07-04T19:57:00.000Z",
  },
  {
    id: 1040,
    flood_node_id: 5,
    flood_node_name: "นิคมอุตสาหกรรมลาดกระบัง",
    flood_node_district: DISTRICT,
    status: "done",
    action_type: "pump_standard",
    assigned_unit: "สถานีสูบน้ำลาดกระบัง",
    notes: "ประชาชนยืนยันน้ำลดแล้ว",
    approved_by: "Coordinator_02",
    confirmed_by: "FieldTeam_03",
    water_level_m: 0.73,
    created_at: "2026-07-04T18:40:00.000Z",
    updated_at: "2026-07-04T19:42:00.000Z",
    dispatched_at: "2026-07-04T18:48:00.000Z",
    line_dispatched: false,
    line_dispatched_at: null,
  },
];

function json(data: unknown, init?: ResponseInit) {
  return Response.json(data, {
    ...init,
    headers: {
      "Cache-Control": "no-store",
      "X-Floodtir-Data-Class": "SIMULATED-by-design",
      ...init?.headers,
    },
  });
}

function pathOf(request: Request) {
  return new URL(request.url).pathname
    .replace(/^\/api\/demo\/?/, "")
    .split("/")
    .filter(Boolean);
}

function nodeFor(id: number) {
  return floodNodes.find((node) => node.id === id);
}

function waterSurface() {
  const wetNodes = floodNodes.filter(
    (node): node is FloodNode & { current_fused_level: number } =>
      node.current_fused_level !== null,
  );
  const points = [];
  const grid = 25;
  const latMin = 13.68;
  const latMax = 13.80;
  const lonMin = 100.73;
  const lonMax = 100.86;
  const dlat = (latMax - latMin) / grid;
  const dlon = (lonMax - lonMin) / grid;

  for (let row = 0; row < grid; row += 1) {
    for (let col = 0; col < grid; col += 1) {
      const lat = latMin + (row + 0.5) * dlat;
      const lon = lonMin + (col + 0.5) * dlon;
      let weighted = 0;
      let totalWeight = 0;
      for (const node of wetNodes) {
        const distanceSquared =
          (node.lat - lat) ** 2 + (node.lon - lon) ** 2;
        const weight = 1 / Math.max(distanceSquared, 0.0000001);
        weighted += node.current_fused_level * weight;
        totalWeight += weight;
      }
      points.push({
        lat: Number(lat.toFixed(6)),
        lon: Number(lon.toFixed(6)),
        level: Number((weighted / totalWeight).toFixed(3)),
        dlat: Number((dlat / 2).toFixed(6)),
        dlon: Number((dlon / 2).toFixed(6)),
      });
    }
  }
  return { points };
}

async function sha256(value: string) {
  const digest = await crypto.subtle.digest(
    "SHA-256",
    new TextEncoder().encode(value),
  );
  return Array.from(new Uint8Array(digest))
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

async function ledger() {
  const events = [
    {
      event_type: "WO_CREATED",
      payload: JSON.stringify({
        work_order_id: 1041,
        flood_node: "แยกร่มเกล้า–ลาดกระบัง",
        water_level_m: 0.84,
        approved_by: "Coordinator_01",
      }),
      created_at: "2026-07-04T19:56:00.000Z",
    },
    {
      event_type: "WO_DISPATCHED",
      payload: JSON.stringify({
        work_order_id: 1041,
        confirmed_by: "FieldTeam_01",
        channel: "LINE (demo)",
      }),
      created_at: "2026-07-04T20:04:00.000Z",
    },
    {
      event_type: "VERIFY_OUTCOME",
      payload: JSON.stringify({
        work_order_id: 1040,
        outcome: "VERIFIED",
        verified_by: "Citizen_07",
      }),
      created_at: "2026-07-04T20:12:00.000Z",
    },
    {
      event_type: "WO_CREATED",
      payload: JSON.stringify({
        work_order_id: 1042,
        flood_node: "ชุมชนหลวงแพ่ง",
        water_level_m: 1.12,
        approved_by: "Coordinator_01",
      }),
      created_at: "2026-07-04T20:21:00.000Z",
    },
  ];

  let previous = "0".repeat(64);
  const entries = [];
  for (const [index, event] of events.entries()) {
    const hash = await sha256(
      `${event.event_type}|${event.payload}|${previous}`,
    );
    entries.push({
      id: index + 1,
      ...event,
      prev_hash: previous,
      hash,
      data_class: "SIMULATED-by-design",
    });
    previous = hash;
  }
  return entries;
}

function planFor(node: FloodNode) {
  const level = node.current_fused_level ?? 0;
  const action_type =
    level > 1 ? "pump_emergency" : level > 0.7 ? "pump_high" : "pump_standard";
  return {
    action_type,
    assigned_unit:
      level > 0.9
        ? "สำนักการระบายน้ำ · หน่วยเคลื่อนที่เร็ว 2"
        : "สำนักงานเขตลาดกระบัง · ฝ่ายโยธา",
    water_level_m: node.current_fused_level,
    district: node.district,
    flood_node_name: node.name,
    n_reports: node.n_reports,
  };
}

export async function GET(request: Request) {
  const path = pathOf(request);
  const url = new URL(request.url);

  if (path[0] === "stats") {
    return json({
      flood_node_count: floodNodes.length,
      reports_today: floodNodes.reduce((sum, node) => sum + node.n_reports, 0),
      work_orders_open: workOrders.filter((order) =>
        ["pending", "dispatched"].includes(order.status),
      ).length,
    });
  }

  if (path[0] === "flood-nodes") return json(floodNodes);
  if (path[0] === "water-surface") return json(waterSurface());
  if (path[0] === "ledger") return json(await ledger());

  if (path[0] === "work-orders" && path[1] === "plan-preview") {
    const node = nodeFor(Number(url.searchParams.get("flood_node_id")));
    if (!node) return json({ detail: "flood node not found" }, { status: 404 });
    if (node.n_reports < 2) {
      return json(
        { detail: "G7: ต้องมีรายงานยืนยันอย่างน้อย 2 รายการก่อนสั่งงาน" },
        { status: 422 },
      );
    }
    return json(planFor(node));
  }

  if (path[0] === "work-orders" && path[1] === "line-preview") {
    const nodeName = url.searchParams.get("flood_node_name") ?? "จุดน้ำท่วม";
    const level = url.searchParams.get("water_level_m") ?? "—";
    const action = url.searchParams.get("action_type") ?? "inspect";
    const unit = url.searchParams.get("assigned_unit") ?? "หน่วยปฏิบัติการ";
    return json({
      message: `🌊 Floodtir Design Demo\nจุด: ${nodeName}\nระดับน้ำ: ${level} ม.\nคำสั่ง: ${action}\nหน่วย: ${unit}\n\n[SIMULATED-by-design · ยังไม่ได้ส่ง LINE จริง]`,
    });
  }

  if (path[0] === "work-orders") return json(workOrders);

  return json({ detail: "demo endpoint not found" }, { status: 404 });
}

export async function POST(request: Request) {
  const path = pathOf(request);

  if (path[0] !== "work-orders") {
    return json({ detail: "demo endpoint not found" }, { status: 404 });
  }

  if (path.length === 1) {
    const body = await request.json();
    const node = nodeFor(Number(body.flood_node_id));
    if (!node) return json({ detail: "flood node not found" }, { status: 404 });
    const plan = planFor(node);
    const nextId = Math.max(...workOrders.map((order) => order.id)) + 1;
    const order: WorkOrder = {
      id: nextId,
      flood_node_id: node.id,
      flood_node_name: node.name,
      flood_node_district: node.district,
      status: "pending",
      action_type: body.action_type || plan.action_type,
      assigned_unit: body.assigned_unit || plan.assigned_unit,
      notes: body.notes ?? "สร้างใน Design Demo",
      approved_by: body.approved_by ?? "Coordinator_01",
      confirmed_by: null,
      water_level_m: node.current_fused_level,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      dispatched_at: null,
      line_dispatched: Boolean(body.notify_line),
      line_dispatched_at: body.notify_line ? new Date().toISOString() : null,
    };
    workOrders = [order, ...workOrders];
    return json(order, { status: 201 });
  }

  const id = Number(path[1]);
  const index = workOrders.findIndex((order) => order.id === id);
  if (index < 0) return json({ detail: "work order not found" }, { status: 404 });

  if (path[2] === "confirm") {
    const body = await request.json();
    workOrders[index] = {
      ...workOrders[index],
      status: "dispatched",
      confirmed_by: body.confirmed_by ?? "FieldTeam_01",
      dispatched_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
    return json(workOrders[index]);
  }

  if (path[2] === "verify") {
    const body = await request.json();
    const mismatch = body.outcome === "MISMATCH";
    workOrders[index] = {
      ...workOrders[index],
      status: mismatch ? "mismatch" : "done",
      updated_at: new Date().toISOString(),
    };
    let newId: number | null = null;
    if (mismatch) {
      newId = Math.max(...workOrders.map((order) => order.id)) + 1;
      workOrders = [
        {
          ...workOrders[index],
          id: newId,
          status: "pending",
          action_type: "pump_emergency",
          notes: `Escalated from WO#${id} after MISMATCH`,
          confirmed_by: null,
          dispatched_at: null,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        },
        ...workOrders,
      ];
    }
    return json({
      id: Date.now(),
      work_order_id: id,
      outcome: body.outcome,
      verified_by: body.verified_by,
      created_at: new Date().toISOString(),
      new_work_order_id: newId,
    }, { status: 201 });
  }

  if (path[2] === "notify-line") {
    workOrders[index] = {
      ...workOrders[index],
      line_dispatched: true,
      line_dispatched_at: new Date().toISOString(),
    };
    return json(workOrders[index]);
  }

  return json({ detail: "demo endpoint not found" }, { status: 404 });
}

export async function PATCH(request: Request) {
  const path = pathOf(request);
  const id = Number(path[1]);
  const index = workOrders.findIndex((order) => order.id === id);
  if (path[0] !== "work-orders" || index < 0) {
    return json({ detail: "work order not found" }, { status: 404 });
  }
  const body = await request.json();
  workOrders[index] = {
    ...workOrders[index],
    ...body,
    updated_at: new Date().toISOString(),
    resend_required: workOrders[index].line_dispatched,
  };
  return json(workOrders[index]);
}
