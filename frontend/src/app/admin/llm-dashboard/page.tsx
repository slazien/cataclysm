"use client";

import { AdminGate } from "@/components/admin/AdminGate";
import { LlmCostDashboard } from "@/components/admin/LlmCostDashboard";

export default function LlmDashboardPage() {
  return (
    <AdminGate>
      <LlmCostDashboard />
    </AdminGate>
  );
}
