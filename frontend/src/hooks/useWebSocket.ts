import { useEffect, useRef } from "react";
import { useAuthStore } from "../store/authStore";
import { useChatStore } from "../store/chatStore";

const WS_URL = import.meta.env.VITE_WS_URL || "ws://localhost:8000/ws";

let globalWs: WebSocket | null = null;

export function useWebSocket() {
  const accessToken = useAuthStore((state) => state.accessToken);
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const reconnectAttempts = useRef(0);
  const reconnectTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!isAuthenticated || !accessToken) {
      if (globalWs) {
        globalWs.close(1000, "User logged out");
        globalWs = null;
      }
      return;
    }

    const connect = () => {
      if (globalWs?.readyState === WebSocket.OPEN) return;

      const url = `${WS_URL}?token=${accessToken}`;
      const socket = new WebSocket(url);
      globalWs = socket;

      socket.onopen = () => {
        reconnectAttempts.current = 0;
        if (reconnectTimeout.current) clearTimeout(reconnectTimeout.current);
      };

      socket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data as string) as {
            type: string;
            payload: Record<string, unknown>;
          };
          const { type, payload } = data;

          // Get fresh state on every message to avoid stale closures
          const store = useChatStore.getState();

          switch (type) {
            case "new_message": {
              const message = payload as unknown as Parameters<typeof store.addMessage>[0];
              store.addMessage(message);
              const isActive = store.activeConversationId === message.conversation_id;
              store.updateLastMessage(
                message.conversation_id,
                message,
                isActive ? 0 : 1
              );
              // Move conversation to top
              store.updateConversationOrder(message.conversation_id);
              break;
            }
            case "typing_start":
              store.setTyping(
                payload.conversation_id as string,
                payload.user_id as string,
                true
              );
              break;
            case "typing_stop":
              store.setTyping(
                payload.conversation_id as string,
                payload.user_id as string,
                false
              );
              break;
            case "user_online":
              store.setUserOnline(payload.user_id as string);
              break;
            case "user_offline":
              store.setUserOffline(payload.user_id as string);
              break;
            case "message_seen":
              // payload: {message_id, user_id, seen_at}
              store.markConversationAsRead(
                payload.conversation_id as string,
                payload.user_id as string
              );
              break;
            case "connected": {
              console.log("WS Connected:", payload.message, payload.user_id);
              // Load the list of friends who are already online when we first connect.
              // Reset the online list so stale entries from previous session are cleared,
              // then set all currently-online friends.
              const onlineFriends = (payload.online_friends as string[]) || [];
              useChatStore.setState({ onlineUsers: onlineFriends });
              break;
            }
            case "error":
              console.error("WS Error:", payload.message);
              break;
            case "pong":
              break;
            default:
              console.warn("Unknown WS event:", type);
          }
        } catch (err) {
          console.error("Failed to parse WS message", err);
        }
      };

      socket.onclose = (event) => {
        if (globalWs !== socket) return;
        globalWs = null;

        if (event.code !== 1000) {
          if (event.code === 1006) {
            import("../api/axios").then((module) => {
              module.default.get("/auth/me").catch(() => {
                // Interceptor handles refresh / logout if needed
              });
            });
          }

          const attempt = reconnectAttempts.current;
          if (attempt < 5) {
            // Exponential backoff: 1s, 2s, 4s, 8s, 16s
            const timeout = Math.pow(2, attempt) * 1000;
            console.log(`WS reconnecting in ${timeout}ms...`);
            reconnectTimeout.current = setTimeout(() => {
              reconnectAttempts.current += 1;
              connect();
            }, timeout);
          } else {
            console.log("Max WS reconnect attempts reached.");
          }
        }
      };

      socket.onerror = (error) => {
        if (globalWs !== socket) return;
        console.error("WebSocket error:", error);
      };
    };

    connect();

    const pingInterval = setInterval(() => {
      if (globalWs?.readyState === WebSocket.OPEN) {
        globalWs.send(JSON.stringify({ type: "ping" }));
      }
    }, 25000);

    return () => {
      if (globalWs) {
        const oldWs = globalWs;
        globalWs = null;
        oldWs.close(1000, "Component unmounted");
      }
      if (reconnectTimeout.current) clearTimeout(reconnectTimeout.current);
      clearInterval(pingInterval);
    };
  }, [accessToken, isAuthenticated]);
}

export const sendMessage = (
  conversationId: string,
  content: string,
  replyToId: string | null = null
): boolean => {
  if (globalWs?.readyState === WebSocket.OPEN) {
    globalWs.send(
      JSON.stringify({
        type: "send_message",
        payload: { conversation_id: conversationId, content, reply_to_id: replyToId },
      })
    );
    return true;
  }
  return false;
};

export const sendTypingStart = (conversationId: string) => {
  if (globalWs?.readyState === WebSocket.OPEN) {
    globalWs.send(
      JSON.stringify({
        type: "typing_start",
        payload: { conversation_id: conversationId },
      })
    );
  }
};

export const sendTypingStop = (conversationId: string) => {
  if (globalWs?.readyState === WebSocket.OPEN) {
    globalWs.send(
      JSON.stringify({
        type: "typing_stop",
        payload: { conversation_id: conversationId },
      })
    );
  }
};

/**
 * Sends mark_seen for a SINGLE message_id (backend expects string, not array).
 */
export const sendMarkSeen = (conversationId: string, messageId: string) => {
  if (globalWs?.readyState === WebSocket.OPEN) {
    globalWs.send(
      JSON.stringify({
        type: "mark_seen",
        payload: { conversation_id: conversationId, message_id: messageId },
      })
    );
  }
};
