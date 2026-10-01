"use client";
import { Workspace } from "@/components/workspace";
export default function ChatPage() {
  return (
    <main id="main" className="chat-only-page">
      <h1 className="chat-page-title">Anisotropy AI chat</h1>
      <Workspace
        activeTab="assistant"
        setActiveTab={() => {}}
        standalone
        chatOnly
      />
    </main>
  );
}
