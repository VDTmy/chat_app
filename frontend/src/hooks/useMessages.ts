import { useState, useEffect, useRef, useCallback } from "react";
import { useShallow } from "zustand/react/shallow";
import axiosInstance from "../api/axios";
import { useChatStore } from "../store/chatStore";
import type { Message } from "../types";

/** Shape returned by GET /conversations/{id}/messages */
interface MessageListResponse {
  messages: Message[];
  has_more: boolean;
  next_cursor: string | null;
}

export function useMessages(conversationId: string | null) {
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(true);

  // Stable empty array — never changes reference, so ?? EMPTY never triggers re-render
  const emptyRef = useRef<Message[]>([]);

  // useShallow compares shallowly: array of same items → same reference → no re-render.
  // Selector returns undefined (not []) when no conversationId — undefined is a primitive,
  // so Object.is(undefined, undefined) === true → no spurious re-render.
  const rawMessages = useChatStore(
    useShallow((state) =>
      conversationId ? state.messages[conversationId] : undefined
    )
  );
  const messages: Message[] = rawMessages ?? emptyRef.current;

  const fetchingForRef = useRef<string | null>(null);

  useEffect(() => {
    if (!conversationId) {
      setIsLoading(false);
      fetchingForRef.current = null;
      return;
    }

    if (fetchingForRef.current === conversationId) {
      // Already fetched for this conversation — but check whether store still has data.
      // After logout → resetChat() wipes messages, so we must re-fetch on re-login.
      const existing = useChatStore.getState().messages[conversationId];
      if (existing && existing.length > 0) return; // data present → skip
      // No data in store → reset guard and fall through to fetch
      fetchingForRef.current = null;
    }
    fetchingForRef.current = conversationId;

    setIsLoading(true);
    setHasMore(true);

    const capturedId = conversationId;

    axiosInstance
      .get<MessageListResponse>(
        `/conversations/${capturedId}/messages?limit=30`
      )
      .then((res) => {
        if (fetchingForRef.current !== capturedId) return;

        // API returns MessageListResponse: { messages: [], has_more: bool, next_cursor: str }
        const fetched: Message[] = res.data?.messages ?? [];

        console.log(
          `[useMessages] conv=${capturedId} fetched=${fetched.length}`,
          fetched[0] ?? "(empty)"
        );

        // Backend newest-first → reverse to oldest-first for rendering
        useChatStore.getState().setMessages(capturedId, [...fetched].reverse());
        setHasMore(res.data?.has_more ?? fetched.length >= 30);
        setIsLoading(false);
      })
      .catch((err: unknown) => {
        if (fetchingForRef.current !== capturedId) return;
        console.error("Failed to fetch messages:", err);
        setIsLoading(false);
      });

    return () => {
      if (fetchingForRef.current === capturedId) {
        fetchingForRef.current = null;
      }
    };
  }, [conversationId]);

  const loadMore = useCallback(async (): Promise<void> => {
    if (!conversationId || isLoadingMore || !hasMore) return;

    const currentMessages =
      useChatStore.getState().messages[conversationId] ?? [];
    if (currentMessages.length === 0) return;

    // Use the oldest message id as cursor for pagination
    const oldestMessageId = currentMessages[0].id;

    setIsLoadingMore(true);
    try {
      const res = await axiosInstance.get<MessageListResponse>(
        `/conversations/${conversationId}/messages?limit=30&cursor=${oldestMessageId}`
      );
      const fetched: Message[] = res.data?.messages ?? [];
      setHasMore(res.data?.has_more ?? fetched.length >= 30);

      if (fetched.length > 0) {
        useChatStore
          .getState()
          .prependMessages(conversationId, [...fetched].reverse());
      }
    } catch (err) {
      console.error("Failed to load more messages:", err);
    } finally {
      setIsLoadingMore(false);
    }
  }, [conversationId, isLoadingMore, hasMore]);

  return { messages, isLoading, isLoadingMore, hasMore, loadMore };
}
