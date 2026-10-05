import { useState, useEffect, useRef } from "react";
import axiosInstance from "../api/axios";
import { useChatStore } from "../store/chatStore";
import { useAuthStore } from "../store/authStore";
import type { Conversation } from "../types";

export function useConversations() {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Read conversations from store reactively
  const conversations = useChatStore((state) => state.conversations);

  // Track user id to detect login/logout so we refetch on re-login
  const userId = useAuthStore((state) => state.user?.id);

  // Guard to fetch only once per user session (avoids Strict Mode double-fetch loop)
  const hasFetchedRef = useRef(false);
  const lastUserIdRef = useRef<string | undefined>(undefined);

  useEffect(() => {
    // When the user changes (logout → re-login), reset the fetch guard
    if (lastUserIdRef.current !== userId) {
      hasFetchedRef.current = false;
      lastUserIdRef.current = userId;
    }

    if (hasFetchedRef.current) return;
    if (!userId) return; // Not authenticated yet, skip
    hasFetchedRef.current = true;

    setIsLoading(true);
    setError(null);

    axiosInstance
      .get<Conversation[]>("/conversations")
      .then((res) => {
        // Use getState() — stable reference, never causes re-render
        useChatStore.getState().setConversations(res.data);
        // Debug: check if members[] is included in list response
        if (res.data.length > 0) {
          console.log(
            "[useConversations] sample:",
            res.data[0].id,
            "members:", res.data[0].members?.length ?? "MISSING"
          );
        }
      })
      .catch((err: unknown) => {
        const message =
          err instanceof Error ? err.message : "Failed to load conversations";
        setError(message);
        console.error("Error fetching conversations:", err);
      })
      .finally(() => {
        setIsLoading(false);
      });
  }, [userId]); // ← re-run when userId changes (covers login/logout/re-login)

  const refetch = () => {
    hasFetchedRef.current = false;
    setIsLoading(true);
    setError(null);

    axiosInstance
      .get<Conversation[]>("/conversations")
      .then((res) => {
        useChatStore.getState().setConversations(res.data);
        hasFetchedRef.current = true;
      })
      .catch((err: unknown) => {
        const message =
          err instanceof Error ? err.message : "Failed to load conversations";
        setError(message);
        console.error("Error fetching conversations:", err);
      })
      .finally(() => {
        setIsLoading(false);
      });
  };

  return { conversations, isLoading, error, refetch };
}
