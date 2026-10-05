import { create } from "zustand";
import type { Conversation, Message } from "../types";

interface ChatState {
  conversations: Conversation[];
  activeConversationId: string | null;
  messages: Record<string, Message[]>; // conversationId → messages (oldest first)
  typingUsers: Record<string, string[]>; // conversationId → array of userIds
  onlineUsers: string[];

  setConversations: (conversations: Conversation[]) => void;
  setActiveConversation: (id: string | null) => void;
  setMessages: (conversationId: string, messages: Message[]) => void;
  /** Prepend older messages at the top (for infinite scroll / load more) */
  prependMessages: (conversationId: string, olderMessages: Message[]) => void;
  addMessage: (message: Message) => void;
  updateLastMessage: (
    conversationId: string,
    message: Message,
    unreadIncrement: number
  ) => void;
  /** Move conversation with new message to the top of the list */
  updateConversationOrder: (conversationId: string) => void;
  setTyping: (conversationId: string, userId: string, isTyping: boolean) => void;
  setUserOnline: (userId: string) => void;
  setUserOffline: (userId: string) => void;
  markConversationAsRead: (conversationId: string, currentUserId: string) => void;
  /** Reset all chat state — call on logout so stale data isn't shown after re-login */
  resetChat: () => void;
}

export const useChatStore = create<ChatState>((set) => ({
  conversations: [],
  activeConversationId: null,
  messages: {},
  typingUsers: {},
  onlineUsers: [],

  setConversations: (conversations) => set({ conversations }),

  setActiveConversation: (id) => set({ activeConversationId: id }),

  setMessages: (conversationId, newMessages) =>
    set((state) => ({
      messages: { ...state.messages, [conversationId]: newMessages },
    })),

  prependMessages: (conversationId, olderMessages) =>
    set((state) => {
      const existing = state.messages[conversationId] || [];
      // Avoid duplicates by filtering out ids already present
      const existingIds = new Set(existing.map((m) => m.id));
      const deduped = olderMessages.filter((m) => !existingIds.has(m.id));
      return {
        messages: {
          ...state.messages,
          [conversationId]: [...deduped, ...existing],
        },
      };
    }),

  addMessage: (message) =>
    set((state) => {
      const convMessages = state.messages[message.conversation_id] || [];
      if (convMessages.some((m) => m.id === message.id)) {
        return state;
      }
      return {
        messages: {
          ...state.messages,
          [message.conversation_id]: [...convMessages, message],
        },
      };
    }),

  updateLastMessage: (conversationId, message, unreadIncrement) =>
    set((state) => {
      const updatedConversations = state.conversations.map((c) => {
        if (c.id === conversationId) {
          return {
            ...c,
            last_message: message,
            unread_count: Math.max(0, (c.unread_count || 0) + unreadIncrement),
          };
        }
        return c;
      });
      return { conversations: updatedConversations };
    }),

  updateConversationOrder: (conversationId) =>
    set((state) => {
      const idx = state.conversations.findIndex((c) => c.id === conversationId);
      if (idx <= 0) return state; // already first or not found
      const updated = [...state.conversations];
      const [conv] = updated.splice(idx, 1);
      return { conversations: [conv, ...updated] };
    }),

  setTyping: (conversationId, userId, isTyping) =>
    set((state) => {
      const currentTyping = state.typingUsers[conversationId] || [];
      const newTyping = isTyping
        ? Array.from(new Set([...currentTyping, userId]))
        : currentTyping.filter((id) => id !== userId);
      return {
        typingUsers: { ...state.typingUsers, [conversationId]: newTyping },
      };
    }),

  setUserOnline: (userId) =>
    set((state) => ({
      onlineUsers: Array.from(new Set([...state.onlineUsers, userId])),
    })),

  setUserOffline: (userId) =>
    set((state) => ({
      onlineUsers: state.onlineUsers.filter((id) => id !== userId),
    })),

  markConversationAsRead: (conversationId, currentUserId) =>
    set((state) => {
      const convMessages = state.messages[conversationId];
      if (!convMessages) return state;

      let changed = false;
      const updatedMessages = convMessages.map((m) => {
        if (!m.is_read && m.sender_id !== currentUserId) {
          changed = true;
          return { ...m, is_read: true };
        }
        return m;
      });

      const updatedConversations = state.conversations.map((c) =>
        c.id === conversationId ? { ...c, unread_count: 0 } : c
      );

      if (!changed) return { conversations: updatedConversations };

      return {
        messages: {
          ...state.messages,
          [conversationId]: updatedMessages,
        },
        conversations: updatedConversations,
      };
    }),

  resetChat: () =>
    set({
      conversations: [],
      activeConversationId: null,
      messages: {},
      typingUsers: {},
      onlineUsers: [],
    }),
}));
