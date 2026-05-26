import { AuthGuard } from "@/components/auth-guard";
import { ChatPanel } from "@/components/chat-panel";

export default function HomePage() {
  return (
    <AuthGuard>
      <ChatPanel />
    </AuthGuard>
  );
}
