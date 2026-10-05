import axiosInstance from "./axios";

export interface MessagePerMinuteMetric {
  window_start: string;
  window_end: string;
  message_count: number;
}

export interface ActiveUsersMetric {
  window_start: string;
  window_end: string;
  active_users: number;
}

/** Returned by the new /analytics/conversations endpoint (aggregated over a time window) */
export interface ConversationMetric {
  conversation_id: string;
  message_count: number;
  first_seen: string | null;
  last_seen: string | null;
}

export const getMessagesPerMinute = async (limit = 20): Promise<MessagePerMinuteMetric[]> => {
  const response = await axiosInstance.get<MessagePerMinuteMetric[]>("/analytics/messages-per-minute", {
    params: { limit },
  });
  return response.data;
};

export const getActiveUsersPerMinute = async (limit = 20): Promise<ActiveUsersMetric[]> => {
  const response = await axiosInstance.get<ActiveUsersMetric[]>("/analytics/active-users", {
    params: { limit },
  });
  return response.data;
};

/**
 * Fetch top conversations aggregated over the last `minutes` minutes.
 * Returns at most `top` conversations sorted by total message count desc.
 */
export const getMessagesPerConversation = async (
  minutes = 20,
  top = 10
): Promise<ConversationMetric[]> => {
  const response = await axiosInstance.get<ConversationMetric[]>("/analytics/conversations", {
    params: { minutes, top },
  });
  return response.data;
};
