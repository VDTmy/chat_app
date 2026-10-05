import { useEffect, useRef, useCallback } from "react";
import { useAuthStore } from "../store/authStore";
import { useChatStore } from "../store/chatStore";

const WS_URL = import.meta.env.VITE_WS_URL || "ws://localhost:8000/ws";

export function useWebSocket() {
  const ws = useRef<WebSocket | null>(null);
  const reconnectTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttempts = useRef(0);

  const accessToken = useAuthStore((state) => state.accessToken);
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);

  const addMessage = useChatStore((state) => state.addMessage);
  const setTyping = useChatStore((state) => state.setTyping);

  const connect = useCallback(() => {
    if (!isAuthenticated || !accessToken) return;

    if (ws.current?.readyState === WebSocket.OPEN) return;

    const url = `${WS_URL}?token=${accessToken}`;
    const socket = new WebSocket(url);

    socket.onopen = () => {
      console.log("WebSocket connected");
      reconnectAttempts.current = 0;
      if (reconnectTimeout.current) clearTimeout(reconnectTimeout.current);
    };

    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        const { type, payload } = data;

        switch (type) {
          case "new_message":
            addMessage(payload);
            break;
          case "typing_start":
            setTyping(payload.conversation_id, payload.user_id, true);
            break;
          case "typing_stop":
            setTyping(payload.conversation_id, payload.user_id, false);
            break;
          case "user_online":
            // TODO: update user status in global users store / list
            console.log("User online", payload.user_id);
            break;
          case "user_offline":
            // TODO: update user status in global users store / list
            console.log("User offline", payload.user_id);
            break;
          case "message_seen":
            // TODO: update message read status
            break;
          case "pong":
            // Heartbeat response
            break;
          case "connected":
            console.log("WS Authenticated:", payload.user_id);
            break;
          case "error":
            console.error("WS Error:", payload.message);
            break;
          default:
            console.warn("Unknown WS event:", type);
        }
      } catch (err) {
        console.error("Failed to parse WS message", err);
      }
    };

    socket.onclose = (event) => {
      // Ignore if this is an old or unmounted socket
      if (ws.current !== socket) return;

      console.log("WebSocket disconnected", event.code, event.reason);
      ws.current = null;

      // Auto reconnect with exponential backoff if not closed normally
      if (event.code !== 1000) {
        // Try to trigger a token refresh via Axios if the connection was abruptly closed
        // This handles the case where the JWT token expired (which FastAPI rejects with 403 -> WS 1006)
        if (event.code === 1006) {
          import("../api/axios").then((module) => {
            module.default.get("/auth/me").catch(() => {
              // Ignore error, interceptor handles the refresh and logout if it fails
            });
          });
        }

        const timeout = Math.min(1000 * 2 ** reconnectAttempts.current, 30000);
        console.log(`Reconnecting in ${timeout}ms...`);
        reconnectTimeout.current = setTimeout(() => {
          reconnectAttempts.current += 1;
          connect();
        }, timeout);
      }
    };

    socket.onerror = (error) => {
      if (ws.current !== socket) return;
      console.error("WebSocket error:", error);
      // Let onclose handle the reconnect
    };

    ws.current = socket;
  }, [accessToken, isAuthenticated, addMessage, setTyping]);

  useEffect(() => {
    connect();

    // Heartbeat mechanism to keep connection alive
    const pingInterval = setInterval(() => {
      if (ws.current?.readyState === WebSocket.OPEN) {
        ws.current.send(JSON.stringify({ type: "ping" }));
      }
    }, 15000); // every 15s

    return () => {
      if (ws.current) {
        const oldWs = ws.current;
        ws.current = null;
        oldWs.close(1000, "Component unmounted");
      }
      if (reconnectTimeout.current) {
        clearTimeout(reconnectTimeout.current);
      }
      clearInterval(pingInterval);
    };
  }, [connect]);

  const sendMessage = useCallback((conversationId: string, content: string) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(
        JSON.stringify({
          type: "send_message",
          payload: { conversation_id: conversationId, content },
        })
      );
    }
  }, []);

  const sendTyping = useCallback((conversationId: string, isTyping: boolean) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(
        JSON.stringify({
          type: isTyping ? "typing_start" : "typing_stop",
          payload: { conversation_id: conversationId },
        })
      );
    }
  }, []);

  const sendMarkSeen = useCallback((messageIds: string[], conversationId: string) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(
        JSON.stringify({
          type: "mark_seen",
          payload: { message_ids: messageIds, conversation_id: conversationId },
        })
      );
    }
  }, []);

  return { ws: ws.current, sendMessage, sendTyping, sendMarkSeen };
}
