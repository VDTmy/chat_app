import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { Sidebar } from "../components/Sidebar";
import { ChatWindow } from "../components/ChatWindow";
import { useChatStore } from "../store/chatStore";
import axiosInstance from "../api/axios";
import type { Conversation } from "../types";

export function ChatPage() {
  const { conversationId } = useParams<{ conversationId?: string }>();


  // On mobile: "sidebar" or "chat" view
  const [mobileView, setMobileView] = useState<"sidebar" | "chat">("sidebar");

  // Sync URL param → store active conversation
  useEffect(() => {
    const { setActiveConversation } = useChatStore.getState();
    if (conversationId) {
      setActiveConversation(conversationId);
      setMobileView("chat");
    } else {
      setActiveConversation(null);
      setMobileView("sidebar");
    }
  }, [conversationId]);

  // Fetch full conversation detail when active conversation changes.
  // The list endpoint may omit members[] — this merges full data into the store.
  useEffect(() => {
    if (!conversationId) return;
    axiosInstance
      .get<Conversation>(`/conversations/${conversationId}`)
      .then((res) => {
        const store = useChatStore.getState();
        const updated = store.conversations.map((c) =>
          c.id === conversationId ? { ...c, ...res.data } : c
        );
        store.setConversations(updated);
      })
      .catch(console.error);
  }, [conversationId]);

  return (
    <div className="flex h-screen w-screen bg-[#0f0f17] overflow-hidden">
      {/* ── Sidebar ── */}
      {/* Desktop: always visible. Mobile: toggle */}
      <div
        className={`
          h-full flex-shrink-0
          md:flex
          ${mobileView === "sidebar" ? "flex" : "hidden"}
          md:w-80 w-full
        `}
      >
        <Sidebar onConversationSelect={() => setMobileView("chat")} />
      </div>

      {/* ── Chat Window ── */}
      <div
        className={`
          flex-1 h-full min-w-0
          md:flex
          ${mobileView === "chat" ? "flex" : "hidden"}
          flex-col
        `}
      >
        <ChatWindow onBack={() => setMobileView("sidebar")} />
      </div>
    </div>
  );
}
