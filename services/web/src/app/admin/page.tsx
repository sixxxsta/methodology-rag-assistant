import { AdminGuard } from "@/components/admin-guard";
import { AdminPanel } from "@/components/admin-panel";

export default function AdminPage() {
  return (
    <AdminGuard>
      <AdminPanel />
    </AdminGuard>
  );
}
